"""API schema placeholder for "deals".

There is no `Deal` domain entity or table yet: genuine deal/discount identification depends on
price-drop detection (`ROADMAP.md` Phase 4) and sale-event intelligence (Phase 7), neither of
which are in scope for Phase 2. This module exists only so `/api/v1/deals` (see
`app/api/v1/deals.py`) has a well-typed response contract to grow into once that logic exists,
per `DEVELOPMENT_RULES.md` §1.2 (never implement a future phase's business logic).
"""

from pydantic import BaseModel, ConfigDict


class DealRead(BaseModel):
    """Intentionally empty placeholder shape. No deal has ever been produced by this schema."""

    model_config = ConfigDict(extra="forbid")
