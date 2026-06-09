"""Backend factory — returns SqliteBackend or SheetsBackend based on config."""

import os

from dotenv import load_dotenv

load_dotenv()

from db import SqliteBackend
from sheets import SheetsBackend


def get_backend() -> SqliteBackend | SheetsBackend:
    """Return the configured backend.

    Set BACKEND=sheets and provide PRICE_LIST_SHEET_ID + GOOGLE_CREDENTIALS_PATH
    to use Google Sheets. Defaults to SQLite.
    """
    backend_type = os.getenv('BACKEND', 'sqlite')

    if backend_type == 'sheets':
        sheet_id = os.getenv('PRICE_LIST_SHEET_ID', '')
        return SheetsBackend(sheet_id)
    else:
        db_path = os.getenv('DB_PATH', 'pricelist.db')
        return SqliteBackend(db_path)
