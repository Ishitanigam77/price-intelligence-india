"""Scalable background data collection (Phase 13)."""

from app.collectors.config import CollectionConfig, collection_config_from_settings
from app.collectors.metrics import (
    JOB_DURATION,
    JOBS_FAILED,
    JOBS_SUCCESSFUL,
    JOBS_TOTAL,
    PRICE_FRESHNESS,
    RETAILER_HEALTH,
)
from app.collectors.orchestrator import CollectionOrchestrator, CollectionRunResult

__all__ = [
    "CollectionConfig",
    "CollectionOrchestrator",
    "CollectionRunResult",
    "JOBS_TOTAL",
    "JOBS_FAILED",
    "JOBS_SUCCESSFUL",
    "JOB_DURATION",
    "RETAILER_HEALTH",
    "PRICE_FRESHNESS",
    "collection_config_from_settings",
]
