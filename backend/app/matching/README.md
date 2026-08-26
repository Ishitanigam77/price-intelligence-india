# app/matching/

Product matching engine: decides whether two retailer-agnostic listings represent the same
physical product and exact variant, a possible match, a different product, or a case that
needs manual review.

**Status**: implemented in this increment (product identity and matching engine). Independent
of FastAPI routes and of specific retailer adapters. Does not persist match results, does not
change discovery persistence, and does not modify adapter behaviour.

## Pipeline

Comparisons run through four stages, in order. Later stages cannot override a hard conflict
found earlier.

1. **Exact identifiers** — GTIN / EAN / UPC / ISBN / MPN / model number, after format
   normalization. Missing identifiers are never treated as a match. Conflicting strong
   identifiers are never ignored.
2. **Normalized attributes** — brand, model, RAM, storage, size, color, capacity, generation,
   variant. Variant disagreements (8 GB vs 16 GB RAM, 128 GB vs 256 GB storage, black vs white,
   different generation, accessory vs primary product) prevent `SAME_PRODUCT`.
3. **Normalized title / token similarity** — punctuation, spelling, word order, and common
   formatting differences. **Title similarity alone is never sufficient for `SAME_PRODUCT`.**
4. **Embeddings** — cosine similarity from a replaceable `EmbeddingProvider`. The default
   backend is a deterministic hashing n-gram encoder (no model download). A Sentence
   Transformer backend is available via `MATCHING_EMBEDDING_BACKEND=sentence_transformers` and
   `MATCHING_EMBEDDING_MODEL`. The model is loaded once per process and reused. Embeddings are
   supporting evidence only and never override identifier or variant conflicts.

Every comparison returns `match_score`, `match_method`, `match_confidence`, `classification`
(`SAME_PRODUCT` | `POSSIBLE_MATCH` | `DIFFERENT_PRODUCT` | `NEEDS_REVIEW`), stage evidence, an
explanation of which stage produced the decision, and retailer/source provenance from both
sides.

## Using the engine

```python
from app.matching import MatchCandidate, MatchingEngine
from app.matching.models import MatchCandidate as Candidate

engine = MatchingEngine()
result = engine.compare(left_candidate, right_candidate)
# result.classification, result.match_score, result.match_method, result.match_confidence
```

`MatchCandidate.from_normalized_product(...)` projects a Phase 2 `NormalizedProduct` without
importing a specific retailer package.

Configuration is read from `MATCHING_*` environment variables (see `.env.example`). Thresholds
and the embedding backend are injected into the engine; they are not hardcoded in the decision
policy beyond documented defaults.
