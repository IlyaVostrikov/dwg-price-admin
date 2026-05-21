import json
import sqlite3
from datetime import datetime, timezone


class SqliteBackend:
    def __init__(self, db_path: str = 'pricelist.db') -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute('PRAGMA journal_mode=WAL')
        self._conn.execute('PRAGMA foreign_keys=ON')
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.executescript('''
            CREATE TABLE IF NOT EXISTS sections (
                id TEXT PRIMARY KEY,
                title_ru TEXT NOT NULL DEFAULT '',
                icon TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                visible INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS brands (
                id TEXT PRIMARY KEY,
                section_id TEXT NOT NULL,
                title_ru TEXT NOT NULL DEFAULT '',
                subtitle_ru TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                visible INTEGER NOT NULL DEFAULT 1,
                has_dual_pricing INTEGER NOT NULL DEFAULT 0,
                column_headers TEXT NOT NULL DEFAULT '[]',
                price_col_indices TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                brand_id TEXT NOT NULL,
                name_ru TEXT NOT NULL DEFAULT '',
                attrs TEXT NOT NULL DEFAULT '{}',
                price_1 INTEGER NOT NULL DEFAULT 0,
                price_2 INTEGER,
                price_1_original INTEGER NOT NULL DEFAULT 0,
                price_2_original INTEGER,
                visible INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS markup_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT '',
                scope_type TEXT NOT NULL DEFAULT '',
                scope_id TEXT NOT NULL DEFAULT '',
                percent REAL NOT NULL DEFAULT 0,
                affected_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );
        ''')
        self._conn.commit()

    # ---- Helpers ----

    def _row_to_dict(self, row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        return dict(row)

    def _rows_to_dicts(self, rows: list[sqlite3.Row]) -> list[dict]:
        return [dict(r) for r in rows]

    # ---- Sections ----

    def get_sections(self) -> list[dict]:
        rows = self._conn.execute(
            'SELECT id, title_ru, icon, sort_order, visible FROM sections'
        ).fetchall()
        return [
            {
                'id': r['id'],
                'title_ru': r['title_ru'],
                'icon': r['icon'],
                'sort_order': r['sort_order'],
                'visible': bool(r['visible']),
            }
            for r in rows
        ]

    def get_sections_df(self) -> list[list]:
        rows = self._conn.execute(
            'SELECT id, title_ru, icon, sort_order, visible FROM sections'
        ).fetchall()
        return [
            [r['id'], r['title_ru'], r['icon'], str(r['sort_order']),
             str(r['visible']).upper()]
            for r in rows
        ]

    def toggle_section_visibility(self, section_id: str, visible: bool) -> None:
        cur = self._conn.execute(
            'UPDATE sections SET visible = ? WHERE id = ?',
            (int(visible), section_id),
        )
        if cur.rowcount == 0:
            raise ValueError(f'Section not found: {section_id}')
        self._conn.commit()

    # ---- Brands ----

    def get_brands(self, section_id: str | None = None) -> list[dict]:
        if section_id:
            rows = self._conn.execute(
                'SELECT * FROM brands WHERE section_id = ?', (section_id,)
            ).fetchall()
        else:
            rows = self._conn.execute('SELECT * FROM brands').fetchall()
        result = []
        for r in rows:
            result.append({
                'id': r['id'],
                'section_id': r['section_id'],
                'title_ru': r['title_ru'],
                'subtitle_ru': r['subtitle_ru'],
                'sort_order': r['sort_order'],
                'visible': bool(r['visible']),
                'has_dual_pricing': bool(r['has_dual_pricing']),
                'column_headers': json.loads(r['column_headers']),
                'price_col_indices': json.loads(r['price_col_indices']),
            })
        return result

    def toggle_brand_visibility(self, brand_id: str, visible: bool) -> None:
        cur = self._conn.execute(
            'UPDATE brands SET visible = ? WHERE id = ?',
            (int(visible), brand_id),
        )
        if cur.rowcount == 0:
            raise ValueError(f'Brand not found: {brand_id}')
        self._conn.commit()

    def add_brand(self, brand: dict) -> None:
        self._conn.execute(
            'INSERT INTO brands (id, section_id, title_ru, subtitle_ru, '
            'sort_order, visible, has_dual_pricing, column_headers, price_col_indices) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                brand['id'],
                brand['section_id'],
                brand['title_ru'],
                brand.get('subtitle_ru', ''),
                brand.get('sort_order', 0),
                int(brand.get('visible', True)),
                int(brand.get('has_dual_pricing', False)),
                json.dumps(brand.get('column_headers', []), ensure_ascii=False),
                json.dumps(brand.get('price_col_indices', []), ensure_ascii=False),
            ),
        )
        self._conn.commit()

    def delete_brand(self, brand_id: str) -> None:
        self._conn.execute('DELETE FROM products WHERE brand_id = ?', (brand_id,))
        cur = self._conn.execute('DELETE FROM brands WHERE id = ?', (brand_id,))
        if cur.rowcount == 0:
            raise ValueError(f'Brand not found: {brand_id}')
        self._conn.commit()

    # ---- Products ----

    def get_products(
        self,
        brand_id: str | None = None,
        search: str | None = None,
        visible_only: bool = False,
    ) -> list[dict]:
        query = 'SELECT * FROM products WHERE 1=1'
        params: list = []

        if brand_id:
            query += ' AND brand_id = ?'
            params.append(brand_id)
        if visible_only:
            query += ' AND visible = 1'
        if search:
            query += ' AND name_ru LIKE ?'
            params.append(f'%{search}%')

        rows = self._conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            result.append({
                'id': r['id'],
                'brand_id': r['brand_id'],
                'name_ru': r['name_ru'],
                'attrs': json.loads(r['attrs']),
                'price_1': r['price_1'],
                'price_2': r['price_2'],
                'price_1_original': r['price_1_original'],
                'price_2_original': r['price_2_original'],
                'visible': bool(r['visible']),
            })
        return result

    def update_product(self, product_id: int, fields: dict) -> None:
        field_map = {
            'name_ru': 'name_ru',
            'attrs': 'attrs',
            'price_1': 'price_1',
            'price_2': 'price_2',
            'price_1_original': 'price_1_original',
            'price_2_original': 'price_2_original',
            'visible': 'visible',
        }
        sets = []
        params = []
        for field, value in fields.items():
            col = field_map.get(field)
            if col is None:
                continue
            if field == 'attrs':
                value = json.dumps(value, ensure_ascii=False)
            elif field == 'visible':
                value = int(value)
            sets.append(f'{col} = ?')
            params.append(value)
        params.append(product_id)
        cur = self._conn.execute(
            f'UPDATE products SET {", ".join(sets)} WHERE id = ?', params
        )
        if cur.rowcount == 0:
            raise ValueError(f'Product not found: {product_id}')
        self._conn.commit()

    def update_product_visibility(self, product_id: int, visible: bool) -> None:
        self.update_product(product_id, {'visible': visible})

    def add_product(self, product: dict) -> None:
        self._conn.execute(
            'INSERT INTO products (id, brand_id, name_ru, attrs, price_1, price_2, '
            'price_1_original, price_2_original, visible) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                product['id'],
                product['brand_id'],
                product['name_ru'],
                json.dumps(product.get('attrs', {}), ensure_ascii=False),
                product.get('price_1', 0),
                product.get('price_2'),
                product.get('price_1_original', product.get('price_1', 0)),
                product.get('price_2_original', product.get('price_2')),
                int(product.get('visible', True)),
            ),
        )
        self._conn.commit()

    def delete_product(self, product_id: int) -> None:
        cur = self._conn.execute('DELETE FROM products WHERE id = ?', (product_id,))
        if cur.rowcount == 0:
            raise ValueError(f'Product not found: {product_id}')
        self._conn.commit()

    # ---- Batch operations ----

    def batch_update_prices(self, updates: list[dict]) -> None:
        for u in updates:
            self._conn.execute(
                'UPDATE products SET price_1 = ?, price_2 = ? WHERE id = ?',
                (u['price_1'], u.get('price_2'), u['id']),
            )
        self._conn.commit()

    def batch_clear_and_write(
        self, tab: str, header: list[str], rows: list[list]
    ) -> None:
        self._conn.execute(f'DELETE FROM {tab}')
        if not rows:
            self._conn.commit()
            return
        placeholders = ', '.join(['?'] * len(header))
        self._conn.executemany(
            f'INSERT INTO {tab} VALUES ({placeholders})', rows
        )
        self._conn.commit()

    # ---- Markup log ----

    def append_markup_log(self, entry: dict) -> None:
        self._conn.execute(
            'INSERT INTO markup_log (timestamp, scope_type, scope_id, percent, affected_count) '
            'VALUES (?, ?, ?, ?, ?)',
            (
                entry.get('timestamp', datetime.now(timezone.utc).isoformat()),
                entry.get('scope_type', ''),
                entry.get('scope_id', ''),
                entry.get('percent', 0),
                entry.get('affected_count', 0),
            ),
        )
        self._conn.commit()

    # ---- Config ----

    def get_config(self) -> dict:
        rows = self._conn.execute('SELECT key, value FROM config').fetchall()
        return {r['key']: r['value'] for r in rows}

    def update_config(self, config: dict) -> None:
        for key, value in config.items():
            self._conn.execute(
                'INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)',
                (key, str(value)),
            )
        self._conn.commit()
