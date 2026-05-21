from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from parser import format_price
from sheets import SheetsBackend

TEMPLATE_DIR = Path(__file__).resolve().parent / 'templates'


def generate_html(backend: SheetsBackend) -> str:
    sections = backend.get_sections()
    sections = [s for s in sections if s['visible']]
    sections.sort(key=lambda s: s['sort_order'])

    all_brands = backend.get_brands()
    all_brands = [b for b in all_brands if b['visible']]
    all_brands.sort(key=lambda b: (b['section_id'], b['sort_order']))

    all_products = backend.get_products(visible_only=True)

    products_by_brand: dict[str, list[dict]] = {}
    for b in all_brands:
        products_by_brand[b['id']] = [
            p for p in all_products if p['brand_id'] == b['id']
        ]

    # Enrich products with formatted prices
    for b in all_brands:
        for p in products_by_brand.get(b['id'], []):
            p['price_1_fmt'] = format_price(
                p['price_1'] if p['price_1'] else None
            )
            p['price_2_fmt'] = format_price(p['price_2'])

    # Compute attr_keys for each brand: column_headers minus name col
    # minus price columns
    for b in all_brands:
        headers = b['column_headers']
        price_indices = set(b['price_col_indices'])
        attr_keys = []
        for i, h in enumerate(headers):
            if i == 0:  # name column
                continue
            if i in price_indices:
                continue
            attr_keys.append(h)
        b['attr_keys'] = attr_keys

    # Counts per section
    counts: dict[str, int] = {}
    for s in sections:
        count = 0
        for b in all_brands:
            if b['section_id'] == s['id']:
                count += len(products_by_brand.get(b['id'], []))
        counts[s['id']] = count

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False,
    )
    template = env.get_template('price_list.html.jinja2')

    return template.render(
        sections=sections,
        brands=all_brands,
        products_by_brand=products_by_brand,
        counts=counts,
    )


def get_html_preview(backend: SheetsBackend, lines: int = 50) -> str:
    html = generate_html(backend)
    html_lines = html.split('\n')
    preview = '\n'.join(html_lines[:lines])
    if len(html_lines) > lines:
        preview += f'\n... (всего {len(html_lines)} строк)'
    return preview
