import json
import os
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup, Tag

from db import SqliteBackend

_PRICE_RE = re.compile(r"(\d[\d\s]*)\s*(?:[рpPР][уy]?[бb]?\.?|₽)")
_PRICE_LABEL_RE = re.compile(
    r'(?:цена|price|стоимость|руб[ль.]|₽)',
    re.IGNORECASE,
)


def parse_price(text: str) -> int | None:
    """'4 360 руб' -> 436000 (kopeks); '—' -> None."""
    if not text:
        return None
    t = text.strip()
    if t in ('—', '-', '', 'нет'):
        return None
    m = _PRICE_RE.search(t)
    if not m:
        return None
    rubles = int(m.group(1).replace(' ', ''))
    return rubles * 100


def format_price(kopeks: int | None) -> str:
    """436000 -> '4 360 ₽'; None -> '—'."""
    if kopeks is None:
        return '—'
    rubles = kopeks // 100
    return f'{rubles:,}'.replace(',', ' ') + ' ₽'


def _is_price_column(header_text: str) -> bool:
    """Check if a table header column is a price column."""
    return bool(_PRICE_LABEL_RE.search(header_text))


def _clean_header(text: str) -> str:
    return text.strip().replace('\n', ' ')


def _slugify(text: str) -> str:
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
        'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k',
        'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
        'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '',
        'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    result = ''
    for ch in text.lower():
        if ch in translit:
            result += translit[ch]
        elif ch.isalnum():
            result += ch
        elif ch in ' -':
            result += '-'
    return re.sub(r'-+', '-', result).strip('-')


class ParsedCatalog:
    def __init__(self) -> None:
        self.sections: list[dict] = []
        self.brands: list[dict] = []
        self.products: list[dict] = []


class PriceListParser:
    def __init__(self, html_path: str) -> None:
        self.html_path = html_path
        self._product_id = 0

    def parse(self) -> ParsedCatalog:
        with open(self.html_path, encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')

        catalog = ParsedCatalog()

        section_els = soup.find_all('section', class_='section')
        for sec in section_els:
            section = self._parse_section(sec)
            if section is None:
                continue
            catalog.sections.append(section)

            brand_els = sec.find_all('article', class_='brand-card')
            for i, art in enumerate(brand_els):
                brand, products = self._parse_brand(art, section['id'], i)
                catalog.brands.append(brand)
                for p in products:
                    catalog.products.append(p)

        return catalog

    def _parse_section(self, sec: Tag) -> dict | None:
        sec_id = sec.get('id', '')
        if not sec_id:
            return None

        head = sec.find('div', class_='section-head')
        h2 = head.find('h2') if head else None
        icon_div = head.find('div', class_='section-icon') if head else None

        title = h2.get_text(strip=True) if h2 else sec_id
        icon = icon_div.get_text(strip=True) if icon_div else ''

        return {
            'id': sec_id,
            'title_ru': title,
            'icon': icon,
            'sort_order': 0,
            'visible': True,
        }

    def _parse_brand(
        self, article: Tag, section_id: str, sort_order: int
    ) -> tuple[dict, list[dict]]:
        head = article.find('div', class_='brand-card-head')
        h3 = head.find('h3') if head else None
        p = head.find('p') if head else None

        title = h3.get_text(strip=True) if h3 else ''
        subtitle = p.get_text(strip=True) if p else ''
        brand_id = _slugify(title) or f'{section_id}-brand-{sort_order}'

        table = article.find('table', class_='price-table')
        if table is None:
            table = article.find('table')

        column_headers: list[str] = []
        price_col_indices: list[int] = []
        has_dual_pricing = False

        if table:
            thead = table.find('thead')
            if thead:
                ths = thead.find_all('th')
                column_headers = []
                for th in ths:
                    text = _clean_header(th.get_text())
                    if text.lower() == 'наименование':
                        text = 'НАИМЕНОВАНИЕ'
                    column_headers.append(text)

                # Detect price columns
                price_cols = []
                for ci, h in enumerate(column_headers):
                    if _is_price_column(h):
                        price_cols.append(ci)
                has_dual_pricing = len(price_cols) >= 2
                price_col_indices = price_cols

        products = self._parse_products(
            table, brand_id, column_headers, price_col_indices
        ) if table else []

        brand = {
            'id': brand_id,
            'section_id': section_id,
            'title_ru': title,
            'subtitle_ru': subtitle,
            'sort_order': sort_order,
            'visible': True,
            'has_dual_pricing': has_dual_pricing,
            'column_headers': column_headers,
            'price_col_indices': price_col_indices,
        }
        return brand, products

    def _parse_products(
        self,
        table: Tag,
        brand_id: str,
        column_headers: list[str],
        price_col_indices: list[int],
    ) -> list[dict]:
        tbody = table.find('tbody')
        if not tbody:
            return []

        products = []
        rows = tbody.find_all('tr')
        for tr in rows:
            cells = tr.find_all('td')
            if not cells:
                continue

            name = cells[0].get_text(strip=True) if len(cells) > 0 else ''

            # Build attrs from non-price, non-name columns
            attrs: dict[str, str] = {}
            for ci, td in enumerate(cells):
                if ci == 0:
                    continue
                if ci in price_col_indices:
                    continue
                if ci < len(column_headers):
                    hdr_name = column_headers[ci]
                    val = td.get_text(strip=True)
                    if val and val not in ('—', '-'):
                        attrs[hdr_name] = val

            # Parse prices
            price_1 = None
            price_2 = None
            if len(price_col_indices) >= 1:
                pi = price_col_indices[0]
                if pi < len(cells):
                    price_1 = parse_price(cells[pi].get_text())
            if len(price_col_indices) >= 2:
                pi = price_col_indices[1]
                if pi < len(cells):
                    price_2 = parse_price(cells[pi].get_text())

            self._product_id += 1
            products.append({
                'id': self._product_id,
                'brand_id': brand_id,
                'name_ru': name,
                'attrs': attrs,
                'price_1': price_1 or 0,
                'price_2': price_2,
                'price_1_original': price_1 or 0,
                'price_2_original': price_2,
                'visible': True,
            })

        return products


def import_to_db(
    html_path: str, backend: SqliteBackend
) -> dict:
    parser = PriceListParser(html_path)
    catalog = parser.parse()

    # Sort section ids
    sort_map = {'coffee': 1, 'tea': 2, 'milk': 3, 'syrups': 4, 'water': 5}
    for s in catalog.sections:
        s['sort_order'] = sort_map.get(s['id'], 0)

    # Write sections
    s_rows = [
        [s['id'], s['title_ru'], s['icon'], str(s['sort_order']),
         str(s['visible']).upper()]
        for s in catalog.sections
    ]
    backend.batch_clear_and_write(
        'sections',
        ['id', 'title_ru', 'icon', 'sort_order', 'visible'],
        s_rows,
    )

    # Write brands
    b_rows = []
    for b in catalog.brands:
        b_rows.append([
            b['id'],
            b['section_id'],
            b['title_ru'],
            b['subtitle_ru'],
            str(b['sort_order']),
            str(b['visible']).upper(),
            str(b['has_dual_pricing']).upper(),
            json.dumps(b['column_headers'], ensure_ascii=False),
            json.dumps(b['price_col_indices'], ensure_ascii=False),
        ])
    backend.batch_clear_and_write(
        'brands',
        ['id', 'section_id', 'title_ru', 'subtitle_ru', 'sort_order',
         'visible', 'has_dual_pricing', 'column_headers', 'price_col_indices'],
        b_rows,
    )

    # Write products
    p_rows = []
    for p in catalog.products:
        p_rows.append([
            str(p['id']),
            p['brand_id'],
            p['name_ru'],
            json.dumps(p['attrs'], ensure_ascii=False),
            str(p['price_1']),
            str(p['price_2']) if p['price_2'] is not None else '',
            str(p['price_1_original']),
            str(p['price_2_original'])
            if p['price_2_original'] is not None else '',
            str(p['visible']).upper(),
        ])
    backend.batch_clear_and_write(
        'products',
        ['id', 'brand_id', 'name_ru', 'attrs', 'price_1', 'price_2',
         'price_1_original', 'price_2_original', 'visible'],
        p_rows,
    )

    # Update config
    backend.update_config({
        'sheet_version': 1,
        'last_import': datetime.now(timezone.utc).isoformat(),
        'source_html_path': html_path,
    })

    return {
        'sections_created': len(catalog.sections),
        'brands_created': len(catalog.brands),
        'products_created': len(catalog.products),
        'errors': [],
    }


if __name__ == '__main__':
    import sys

    from db import SqliteBackend

    db_path = os.getenv('DB_PATH', 'pricelist.db')
    html_path = os.getenv('SOURCE_HTML_PATH', 'Единый прайс.html')

    if not os.path.exists(html_path):
        print(f'HTML file not found: {html_path}')
        sys.exit(1)

    backend = SqliteBackend(db_path)
    result = import_to_db(html_path, backend)
    print(f'Import complete: {result}')
