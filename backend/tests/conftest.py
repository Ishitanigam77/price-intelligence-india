"""Root pytest configuration.

Ensures `DATABASE_URL` points at the test database *before* any `app.*` module is imported for
the first time in the test process, since `app.db.session` builds its engine at import time.
"""

import os

from tests.db_settings import TEST_DATABASE_URL

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
