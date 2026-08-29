"""Inference package: load a versioned model and emit labeled predictions."""

from ml.inference.predict import predict, predict_listing
from ml.inference.registry import LoadedModel, load_model

__all__ = ["LoadedModel", "load_model", "predict", "predict_listing"]
