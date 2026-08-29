"""Environment-sourced Amazon.in Creators API credentials.

Never log these values. Never place them on `RetailerAdapterConfig.options`.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from app.retailer_adapters.amazon_in.config import RETAILER_ID
from app.retailer_adapters.base.config import env_prefix_for
from app.retailer_adapters.base.errors import AdapterMisconfiguredError


@dataclass(frozen=True)
class AmazonInCredentials:
    """OAuth client credentials plus the Associates partner tag for www.amazon.in."""

    credential_id: str
    credential_secret: str
    partner_tag: str


def load_credentials(
    env: Mapping[str, str], *, retailer_id: str = RETAILER_ID
) -> AmazonInCredentials:
    """Read Creators API credentials from `env`. Raises if any required value is missing."""
    prefix = env_prefix_for(retailer_id)
    credential_id = (env.get(f"{prefix}CREDENTIAL_ID") or "").strip()
    credential_secret = (env.get(f"{prefix}CREDENTIAL_SECRET") or "").strip()
    partner_tag = (env.get(f"{prefix}PARTNER_TAG") or "").strip()
    missing = [
        name
        for name, value in (
            (f"{prefix}CREDENTIAL_ID", credential_id),
            (f"{prefix}CREDENTIAL_SECRET", credential_secret),
            (f"{prefix}PARTNER_TAG", partner_tag),
        )
        if not value
    ]
    if missing:
        raise AdapterMisconfiguredError(
            "Amazon.in Creators API credentials are not configured "
            f"({', '.join(missing)}).",
            retailer_id=retailer_id,
        )
    return AmazonInCredentials(
        credential_id=credential_id,
        credential_secret=credential_secret,
        partner_tag=partner_tag,
    )
