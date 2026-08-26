"""Stage 4: embedding similarity behind a replaceable provider interface.

Embeddings are supporting evidence only. They never override identifier conflicts, variant
conflicts, or accessory mismatches. The Sentence Transformer model is loaded once per process
and reused; comparisons do not reload it.
"""

from __future__ import annotations

import hashlib
import math
import threading
from collections import OrderedDict
from collections.abc import Callable, Sequence
from typing import Protocol, runtime_checkable

from app.matching.config import MatchingConfig
from app.observability.logging import get_logger

logger = get_logger(__name__)

Vector = tuple[float, ...]

_MODEL_LOCK = threading.Lock()
_LOADED_MODELS: dict[str, object] = {}


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Cosine similarity in `[0.0, 1.0]` after clamping slightly negative values to 0.

    Product-title embeddings are expected to be non-negative in practice after hashing; a
    negative cosine is treated as 0 rather than inverted into a match signal.
    """
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for left_value, right_value in zip(left, right, strict=True):
        dot += left_value * right_value
        left_norm += left_value * left_value
        right_norm += right_value * right_value
    if left_norm <= 0.0 or right_norm <= 0.0:
        return 0.0
    raw = dot / math.sqrt(left_norm * right_norm)
    if raw < 0.0:
        return 0.0
    if raw > 1.0:
        return 1.0
    return raw


def l2_normalize(values: Sequence[float]) -> Vector:
    norm = math.sqrt(sum(value * value for value in values))
    if norm <= 0.0:
        return tuple(0.0 for _ in values)
    return tuple(value / norm for value in values)


class _LruCache:
    def __init__(self, maxsize: int) -> None:
        self._maxsize = maxsize
        self._data: OrderedDict[str, Vector] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Vector | None:
        if self._maxsize <= 0:
            return None
        with self._lock:
            value = self._data.get(key)
            if value is not None:
                self._data.move_to_end(key)
            return value

    def put(self, key: str, value: Vector) -> None:
        if self._maxsize <= 0:
            return
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Replaceable embedding backend. Implementations must be thread-safe for encode()."""

    @property
    def name(self) -> str:
        """Backend identifier recorded on match evidence (not a secret)."""

    def embed(self, text: str) -> Vector:
        """Return a vector for `text`. Callers may cache at a higher layer."""

    def similarity(self, left_text: str, right_text: str) -> float:
        return cosine_similarity(self.embed(left_text), self.embed(right_text))


class HashingNgramEmbeddingProvider:
    """Deterministic character n-gram hashing encoder.

    Used as the default backend so tests and CI never download a model. Cosine similarity of
    the resulting vectors still rises for overlapping titles and falls for unrelated ones.
    """

    def __init__(self, *, dimension: int = 256, cache_size: int = 2048) -> None:
        if dimension < 8:
            raise ValueError("dimension must be at least 8.")
        self._dimension = dimension
        self._cache = _LruCache(cache_size)

    @property
    def name(self) -> str:
        return f"hashing_ngram:{self._dimension}"

    def embed(self, text: str) -> Vector:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        vector = [0.0] * self._dimension
        padded = f"  {text.lower()}  "
        for ngram_size in (2, 3):
            for index in range(len(padded) - ngram_size + 1):
                gram = padded[index : index + ngram_size]
                digest = hashlib.sha256(gram.encode("utf-8")).digest()
                bucket = int.from_bytes(digest[:4], "little") % self._dimension
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vector[bucket] += sign
        normalized = l2_normalize(vector)
        self._cache.put(text, normalized)
        return normalized

    def similarity(self, left_text: str, right_text: str) -> float:
        return cosine_similarity(self.embed(left_text), self.embed(right_text))


class StaticEmbeddingProvider:
    """Explicit vector table. Unknown texts fall back to a hashing encoder.

    Useful in tests and as a stand-in when swapping backends.
    """

    def __init__(
        self,
        vectors: dict[str, Sequence[float]] | None = None,
        *,
        fallback: EmbeddingProvider | None = None,
        name: str = "static",
    ) -> None:
        self._vectors = {key: l2_normalize(value) for key, value in (vectors or {}).items()}
        self._fallback = fallback or HashingNgramEmbeddingProvider(dimension=32, cache_size=64)
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def embed(self, text: str) -> Vector:
        if text in self._vectors:
            return self._vectors[text]
        return self._fallback.embed(text)

    def similarity(self, left_text: str, right_text: str) -> float:
        return cosine_similarity(self.embed(left_text), self.embed(right_text))


class SentenceTransformerEmbeddingProvider:
    """Lazy, process-cached Sentence Transformer encoder.

    The underlying model object is stored in a module-level cache keyed by model name so
    repeated comparisons (and multiple provider instances) do not reload or re-download it.
    """

    def __init__(
        self,
        model_name: str,
        *,
        cache_size: int = 2048,
        loader: Callable[[str], object] | None = None,
    ) -> None:
        if not model_name.strip():
            raise ValueError("Sentence Transformer model_name must not be blank.")
        self._model_name = model_name.strip()
        self._loader = loader
        self._cache = _LruCache(cache_size)
        self._model: object | None = None

    @property
    def name(self) -> str:
        return f"sentence_transformers:{self._model_name}"

    def _get_model(self) -> object:
        if self._model is not None:
            return self._model
        with _MODEL_LOCK:
            cached = _LOADED_MODELS.get(self._model_name)
            if cached is None:
                loader = self._loader or _default_sentence_transformer_loader
                logger.info(
                    "matching.embedding_model_load",
                    extra={"model_name": self._model_name, "backend": "sentence_transformers"},
                )
                cached = loader(self._model_name)
                _LOADED_MODELS[self._model_name] = cached
            self._model = cached
        return self._model

    def embed(self, text: str) -> Vector:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        model = self._get_model()
        encode = getattr(model, "encode", None)
        if encode is None:
            raise TypeError("Sentence Transformer model must expose an encode() method.")
        raw = encode(text, convert_to_numpy=True, show_progress_bar=False)
        if hasattr(raw, "tolist"):
            raw = raw.tolist()
        if isinstance(raw, float):
            values: Sequence[float] = [float(raw)]
        else:
            values = [float(item) for item in raw]
        normalized = l2_normalize(values)
        self._cache.put(text, normalized)
        return normalized

    def similarity(self, left_text: str, right_text: str) -> float:
        return cosine_similarity(self.embed(left_text), self.embed(right_text))


def _default_sentence_transformer_loader(model_name: str) -> object:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - exercised via a dedicated unit test
        raise ImportError(
            "The sentence_transformers package is not installed. Install the backend extra "
            "'matching' (pip install -e '.[matching]') or set MATCHING_EMBEDDING_BACKEND=hashing."
        ) from exc
    return SentenceTransformer(model_name)


def reset_loaded_sentence_transformer_models() -> None:
    """Test helper: drop the process-level model cache."""
    with _MODEL_LOCK:
        _LOADED_MODELS.clear()


def build_embedding_provider(
    config: MatchingConfig,
    *,
    override: EmbeddingProvider | None = None,
) -> EmbeddingProvider:
    """Construct the configured backend. `override` wins so tests can inject a fake."""
    if override is not None:
        return override
    if config.embedding_backend == "sentence_transformers":
        try:
            return SentenceTransformerEmbeddingProvider(
                config.embedding_model, cache_size=config.embedding_cache_size
            )
        except ImportError:
            logger.warning(
                "matching.embedding_backend_fallback",
                extra={
                    "requested_backend": "sentence_transformers",
                    "fallback_backend": "hashing",
                    "model_name": config.embedding_model,
                },
            )
    return HashingNgramEmbeddingProvider(
        dimension=config.embedding_dimension, cache_size=config.embedding_cache_size
    )
