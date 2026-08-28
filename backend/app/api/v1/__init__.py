"""Aggregates every `/api/v1/*` route module behind a single `api_router`.

`app.main` mounts `api_router` under the configured `api_v1_prefix` (default `/api/v1`). Adding
a new versioned resource means adding a module here and including its router — nothing else in
`app.main` needs to change.
"""

from fastapi import APIRouter

from app.api.v1 import deals, health, prices, products, retailers, sale_events

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(products.router)
api_router.include_router(retailers.router)
api_router.include_router(prices.router)
api_router.include_router(deals.router)
api_router.include_router(sale_events.router)
