"""Environment-sourced Flipkart Affiliate API credentials.

Never log these values. Never place them on `RetailerAdapterConfig.options`.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from app.retailer_adapters.base.config import env_prefix_for
from app.retailer_adapters.base.errors import AdapterMisconfiguredError
from app.retailer_adapters.flipkart.config import RETAILER_ID


@dataclass(frozen=True)
class FlipkartCredentials:
    """Affiliate tracking id and API token for affiliate-api.flipkart.net."""

    affiliate_id: str
    affiliate_token: str


def load_credentials(
    env: Mapping[str, str], *, retailer_id: str = RETAILER_ID
) -> FlipkartCredentials:
    """Read Affiliate API credentials from `env`. Raises if any required value is missing."""
    prefix = env_prefix_for(retailer_id)
    affiliate_id = (env.get(f"{prefix}AFFILIATE_ID") or "").strip()
    affiliate_token = (env.get(f"{prefix}AFFILIATE_TOKEN") or "").strip()
    missing = [
        name
        for name, value in (
            (f"{prefix}AFFILIATE_ID", affiliate_id),
            (f"{prefix}AFFILIATE_TOKEN", affiliate_token),
        )
        if not value
    ]
    if missing:
        raise AdapterMisconfiguredError(
            "Flipkart Affiliate API credentials are not configured "
            f"({', '.join(missing)}).",
            retailer_id=retailer_id,
        )
    return FlipkartCredentials(affiliate_id=affiliate_id, affiliate_token=affiliate_token)
