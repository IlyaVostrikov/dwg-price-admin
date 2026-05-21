import json
import os
from datetime import datetime, timezone
from functools import lru_cache

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


class SheetsBackend:
    def __init__(self, sheet_id: str, credentials_path: str) -> None:
        if not sheet_id:
            raise ValueError('PRICE_LIST_SHEET_ID is not configured')
        if not credentials_path or not os.path.exists(credentials_path):
            raise ValueError(
                f'Service account key not found: {credentials_path}'
            )
        self.sheet_id = sheet_id
        self.creds = Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
        self.service = build('sheets', 'v4', credentials=self.creds)

    def _read_range(self, range_name: str) -> list[list[str]]:
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.sheet_id, range=range_name)
            .execute()
        )
        return result.get('values', [])

    def _write_range(
        self, range_name: str, values: list[list], raw: bool = True
    ) -> None:
        body = {'values': values}
        opts = {'valueInputOption': 'RAW' if raw else 'USER_ENTERED'}
        self.service.spreadsheets().values().update(
            spreadsheetId=self.sheet_id,
            range=range_name,
            valueInputOption=opts['valueInputOption'],
            body=body,
        ).execute()

    def _append_rows(self, range_name: str, values: list[list]) -> None:
        body = {'values': values}
        self.service.spreadsheets().values().append(
            spreadsheetId=self.sheet_id,
            range=range_name,
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body,
        ).execute()

    def _clear_range(self, range_name: str) -> None:
        self.service.spreadsheets().values().clear(
            spreadsheetId=self.sheet_id,
            range=range_name,
        ).execute()

    def _find_row(
        self, tab: str, id_column: int, row_id: str, max_rows: int = 500
    ) -> int | None:
        rows = self._read_range(f'{tab}!A2:A{max_rows}')
        for i, row in enumerate(rows):
            if row and row[0] == row_id:
                return i + 2  # 1-based row number in Sheets
        return None

    # ---- Sections ----

    def get_sections(self) -> list[dict]:
        rows = self._read_range('sections!A2:E50')
        result = []
        for row in rows:
            if not row:
                continue
            result.append({
                'id': row[0] if len(row) > 0 else '',
                'title_ru': row[1] if len(row) > 1 else '',
                'icon': row[2] if len(row) > 2 else '',
                'sort_order': int(row[3]) if len(row) > 3 and row[3] else 0,
                'visible': row[4].upper() == 'TRUE'
                if len(row) > 4 and row[4] else True,
            })
        return result

    def get_sections_df(self) -> list[list]:
        return self._read_range('sections!A2:E50')

    def toggle_section_visibility(self, section_id: str, visible: bool) -> None:
        row_num = self._find_row('sections', 0, section_id)
        if row_num is None:
            raise ValueError(f'Section not found: {section_id}')
        self._write_range(
            f'sections!E{row_num}',
            [[str(visible).upper()]],
        )

    # ---- Brands ----

    def get_brands(self, section_id: str | None = None) -> list[dict]:
        rows = self._read_range('brands!A2:H50')
        result = []
        for row in rows:
            if not row:
                continue
            brand = {
                'id': row[0] if len(row) > 0 else '',
                'section_id': row[1] if len(row) > 1 else '',
                'title_ru': row[2] if len(row) > 2 else '',
                'subtitle_ru': row[3] if len(row) > 3 else '',
                'sort_order': int(row[4]) if len(row) > 4 and row[4] else 0,
                'visible': row[5].upper() == 'TRUE'
                if len(row) > 5 and row[5] else True,
                'has_dual_pricing': row[6].upper() == 'TRUE'
                if len(row) > 6 and row[6] else False,
                'column_headers': json.loads(row[7])
                if len(row) > 7 and row[7] else [],
                'price_col_indices': json.loads(row[7 + 1])
                if len(row) > 8 and row[8] else [],
            }
            if section_id is None or brand['section_id'] == section_id:
                result.append(brand)
        return result

    def toggle_brand_visibility(self, brand_id: str, visible: bool) -> None:
        row_num = self._find_row('brands', 0, brand_id)
        if row_num is None:
            raise ValueError(f'Brand not found: {brand_id}')
        self._write_range(
            f'brands!F{row_num}',
            [[str(visible).upper()]],
        )

    def add_brand(self, brand: dict) -> None:
        row = [
            brand['id'],
            brand['section_id'],
            brand['title_ru'],
            brand.get('subtitle_ru', ''),
            str(brand.get('sort_order', 0)),
            str(brand.get('visible', True)).upper(),
            str(brand.get('has_dual_pricing', False)).upper(),
            json.dumps(brand.get('column_headers', []), ensure_ascii=False),
            json.dumps(brand.get('price_col_indices', []), ensure_ascii=False),
        ]
        self._append_rows('brands!A2:I2', [row])

    def delete_brand(self, brand_id: str) -> None:
        row_num = self._find_row('brands', 0, brand_id)
        if row_num is None:
            raise ValueError(f'Brand not found: {brand_id}')
        self._clear_range(f'brands!A{row_num}:I{row_num}')

    # ---- Products ----

    def get_products(
        self,
        brand_id: str | None = None,
        search: str | None = None,
        visible_only: bool = False,
    ) -> list[dict]:
        rows = self._read_range('products!A2:J1000')
        result = []
        for row in rows:
            if not row:
                continue
            product = {
                'id': int(row[0]) if len(row) > 0 and row[0] else 0,
                'brand_id': row[1] if len(row) > 1 else '',
                'name_ru': row[2] if len(row) > 2 else '',
                'attrs': json.loads(row[3])
                if len(row) > 3 and row[3] else {},
                'price_1': int(row[4]) if len(row) > 4 and row[4] else 0,
                'price_2': int(row[5])
                if len(row) > 5 and row[5] else None,
                'price_1_original': int(row[6])
                if len(row) > 6 and row[6] else 0,
                'price_2_original': int(row[7])
                if len(row) > 7 and row[7] else None,
                'visible': row[8].upper() == 'TRUE'
                if len(row) > 8 and row[8] else True,
            }
            # Filters
            if brand_id and product['brand_id'] != brand_id:
                continue
            if visible_only and not product['visible']:
                continue
            if search and search.lower() not in product['name_ru'].lower():
                continue
            result.append(product)
        return result

    def update_product(self, product_id: int, fields: dict) -> None:
        row_num = self._find_row('products', 0, str(product_id))
        if row_num is None:
            raise ValueError(f'Product not found: {product_id}')

        col_map = {
            'name_ru': 'C',
            'attrs': 'D',
            'price_1': 'E',
            'price_2': 'F',
            'price_1_original': 'G',
            'price_2_original': 'H',
            'visible': 'I',
        }
        for field, value in fields.items():
            col = col_map.get(field)
            if col is None:
                continue
            if field == 'attrs':
                value = json.dumps(value, ensure_ascii=False)
            elif field == 'visible':
                value = str(value).upper()
            else:
                value = str(value) if value is not None else ''
            self._write_range(f'products!{col}{row_num}', [[value]])

    def update_product_visibility(
        self, product_id: int, visible: bool
    ) -> None:
        self.update_product(product_id, {'visible': visible})

    def add_product(self, product: dict) -> None:
        row = [
            str(product['id']),
            product['brand_id'],
            product['name_ru'],
            json.dumps(product.get('attrs', {}), ensure_ascii=False),
            str(product.get('price_1', 0)),
            str(product.get('price_2', ''))
            if product.get('price_2') is not None
            else '',
            str(product.get('price_1_original', product.get('price_1', 0))),
            str(product.get('price_2_original', product.get('price_2', '')))
            if product.get('price_2_original') is not None
            or product.get('price_2') is not None
            else '',
            str(product.get('visible', True)).upper(),
        ]
        self._append_rows('products!A2:J2', [row])

    def delete_product(self, product_id: int) -> None:
        row_num = self._find_row('products', 0, str(product_id))
        if row_num is None:
            raise ValueError(f'Product not found: {product_id}')
        self._clear_range(f'products!A{row_num}:I{row_num}')

    # ---- Batch operations ----

    def batch_update_prices(
        self, updates: list[dict]
    ) -> None:
        """updates: list of {id, price_1, price_2}"""
        for u in updates:
            row_num = self._find_row('products', 0, str(u['id']))
            if row_num is None:
                continue
            values = [
                [str(u['price_1'])],
                [
                    str(u['price_2'])
                    if u.get('price_2') is not None
                    else ''
                ],
            ]
            self._write_range(f'products!E{row_num}:F{row_num}', values)

    def batch_clear_and_write(
        self, tab: str, header: list[str], rows: list[list]
    ) -> None:
        self._clear_range(f'{tab}!A2:Z1000')
        if rows:
            self._write_range(
                f'{tab}!A2',
                rows,
            )

    # ---- Markup log ----

    def append_markup_log(self, entry: dict) -> None:
        row = [
            entry.get('timestamp', datetime.now(timezone.utc).isoformat()),
            entry.get('scope_type', ''),
            entry.get('scope_id', ''),
            str(entry.get('percent', 0)),
            str(entry.get('affected_count', 0)),
        ]
        self._append_rows('markup_log!A2:E2', [row])

    # ---- Config ----

    def get_config(self) -> dict:
        rows = self._read_range('config!A2:C2')
        if not rows or not rows[0]:
            return {
                'sheet_version': 1,
                'last_import': '',
                'source_html_path': '',
            }
        r = rows[0]
        return {
            'sheet_version': int(r[0]) if len(r) > 0 and r[0] else 1,
            'last_import': r[1] if len(r) > 1 else '',
            'source_html_path': r[2] if len(r) > 2 else '',
        }

    def update_config(self, config: dict) -> None:
        row = [
            str(config.get('sheet_version', 1)),
            config.get('last_import', ''),
            config.get('source_html_path', ''),
        ]
        self._write_range('config!A2:C2', [row])
