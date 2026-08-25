"""Single source of truth for the database URL integration tests run against.

The fallback below uses the exact same non-secret placeholder credential as `.env.example`
(never a real one) — set `TEST_DATABASE_URL` to override it for your own local setup.
"""

import os

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://priceradar_app:changeme@localhost:5432/priceradar_test",
)
