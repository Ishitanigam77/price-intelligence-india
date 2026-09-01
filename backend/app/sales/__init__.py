"""Sale-event intelligence: tracks sale windows and historical sale prices.

Independent of FastAPI and of specific retailer adapter packages. Does not predict future
prices. Observed prices, calculated sale statistics, and (absent) predictions stay labeled
separately (`PROJECT_ARCHITECTURE.md` §6).
"""

from app.sales.classification import classify_family
from app.sales.config import SalesConfig, get_sales_config
from app.sales.detection import SaleEventDetector
from app.sales.engine import SaleEventEngine
from app.sales.enums import SaleInsufficientReasonCode
from app.sales.history import SaleHistoryEngine
from app.sales.intelligence import SaleIntelligenceEngine, expected_savings
from app.sales.lifecycle import event_status
from app.sales.models import (
    DetectedSaleWindow,
    ProductSaleHistory,
    SaleEventRecord,
    SaleEventView,
    SalePricePoint,
    VariantSaleHistory,
)
from app.sales.timing_models import (
    TIMING_DISCLAIMER,
    ExpectedSaleWindow,
    ProductSaleIntelligence,
)

__all__ = [
    "DetectedSaleWindow",
    "ExpectedSaleWindow",
    "ProductSaleHistory",
    "ProductSaleIntelligence",
    "SaleEventDetector",
    "SaleEventEngine",
    "SaleEventRecord",
    "SaleEventView",
    "SaleHistoryEngine",
    "SaleInsufficientReasonCode",
    "SaleIntelligenceEngine",
    "SalePricePoint",
    "SalesConfig",
    "TIMING_DISCLAIMER",
    "VariantSaleHistory",
    "classify_family",
    "event_status",
    "expected_savings",
    "get_sales_config",
]
