"""Initialize SQLite database with data from HTML price list.

Usage:
    uv run python init_db.py

Environment variables in .env:
    DB_PATH: path to SQLite database (default: pricelist.db)
    SOURCE_HTML_PATH: path to HTML price list (default: Единый прайс.html)
"""

import os

from dotenv import load_dotenv

from db import SqliteBackend
from parser import import_to_db

load_dotenv()


def main() -> None:
    db_path = os.getenv('DB_PATH', 'pricelist.db')
    html_path = os.getenv('SOURCE_HTML_PATH', 'Единый прайс.html')

    if not os.path.exists(html_path):
        print(f'ERROR: HTML file not found: {html_path}')
        return

    # SqliteBackend.__init__ creates tables automatically
    backend = SqliteBackend(db_path)

    print(f'Parsing {html_path}...')
    result = import_to_db(html_path, backend)

    print(f'Import complete:')
    print(f'  Sections: {result["sections_created"]}')
    print(f'  Brands:   {result["brands_created"]}')
    print(f'  Products: {result["products_created"]}')
    if result.get('errors'):
        print(f'  Errors:   {result["errors"]}')
    print(f'\nDatabase: {db_path}')


if __name__ == '__main__':
    main()
