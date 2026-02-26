"""Database package — re-exports all functions for backward compatibility.

Usage: `import database as db` or `from database import get_pool` still works
because database.py re-exports from this package.
"""

from db.connection import get_pool, init_db, SCHEMA, DATABASE_URL
from db.generations import *  # noqa: F401,F403
from db.analytics import *  # noqa: F401,F403
from db.settings import *  # noqa: F401,F403
from db.schedule import *  # noqa: F401,F403
from db.competitors import *  # noqa: F401,F403
from db.mockups import *  # noqa: F401,F403
from db.products import *  # noqa: F401,F403
from db.seo import *  # noqa: F401,F403
from db.strategy import *  # noqa: F401,F403
from db.tasks import *  # noqa: F401,F403
