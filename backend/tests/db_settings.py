"""Single source of truth for the database URL integration tests run against."""

import os

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://priceradar_app:devpassword_local_only@localhost:5432/priceradar_test",
)
