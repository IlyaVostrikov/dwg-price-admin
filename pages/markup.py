import os
from datetime import datetime, timezone

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from db import SqliteBackend


@st.cache_resource
def get_backend() -> SqliteBackend:
    return SqliteBackend(os.getenv('DB_PATH', 'pricelist.db'))


def apply_markup_price(original_kopeks: int, percent: float) -> int:
    """Apply percentage markup, rounding to nearest ruble."""
    new_rubles = round(original_kopeks / 100 * (1 + percent / 100))
    return new_rubles * 100


st.title('Наценки')

backend = get_backend()

sections = backend.get_sections()
brands = backend.get_brands()

section_map = {s['id']: s for s in sections}
brand_map = {b['id']: b for b in brands}

# ---- Scope selection ----
col1, col2 = st.columns(2)
with col1:
    scope_type = st.radio(
        'Область применения', ['brand', 'section'],
        format_func=lambda x: 'Бренд' if x == 'brand' else 'Секция',
        horizontal=True,
    )
with col2:
    if scope_type == 'section':
        scope_options = {
            s['id']: f'{s["icon"]} {s["title_ru"]}' for s in sections
        }
        scope_id = st.selectbox(
            'Секция', options=list(scope_options.keys()),
            format_func=lambda k: scope_options[k],
        )
        scope_label = section_map[scope_id]['title_ru']
    else:
        # Group brands by section for the selectbox
        scope_options = {}
        for b in brands:
            s = section_map.get(b['section_id'], {})
            scope_options[b['id']] = (
                f'{s.get("icon", "")} {b["title_ru"]}'
            )
        scope_id = st.selectbox(
            'Бренд', options=list(scope_options.keys()),
            format_func=lambda k: scope_options[k],
        )
        scope_label = brand_map[scope_id]['title_ru']

# ---- Percent input ----
percent = st.number_input(
    'Наценка (%)',
    value=0.0,
    step=0.5,
    min_value=-100.0,
    max_value=1000.0,
    help='Положительное значение — увеличение цены, отрицательное — скидка. '
         'Наценка всегда применяется от базовой (оригинальной) цены.',
)

# ---- Get affected products ----
if scope_type == 'section':
    affected_brands = [b for b in brands if b['section_id'] == scope_id]
    affected_products = []
    for b in affected_brands:
        affected_products.extend(
            backend.get_products(brand_id=b['id'], visible_only=True)
        )
else:
    affected_products = backend.get_products(
        brand_id=scope_id, visible_only=True
    )

st.caption(f'Затронуто товаров: {len(affected_products)}')

# ---- Preview ----
if percent != 0 and affected_products:
    st.subheader('Предпросмотр')

    preview_rows = []
    for p in affected_products:
        new_price_1 = apply_markup_price(p['price_1_original'], percent)
        row = {
            'Товар': p['name_ru'],
            'Базовая цена 1': f"{p['price_1_original'] / 100:,.0f}".replace(',', ' '),
            'Текущая цена 1': f"{p['price_1'] / 100:,.0f}" if p['price_1'] else '—',
            'Новая цена 1': f"{new_price_1 / 100:,.0f}".replace(',', ' '),
            'Δ': f"{new_price_1 - p['price_1']:+d}" if p['price_1'] else '—',
        }
        if p['price_2_original'] is not None:
            new_price_2 = apply_markup_price(p['price_2_original'], percent)
            row['Базовая цена 2'] = f"{p['price_2_original'] / 100:,.0f}".replace(',', ' ')
            row['Текущая цена 2'] = f"{p['price_2'] / 100:,.0f}" if p['price_2'] else '—'
            row['Новая цена 2'] = f"{new_price_2 / 100:,.0f}".replace(',', ' ')
        preview_rows.append(row)

    st.dataframe(
        preview_rows,
        use_container_width=True,
        hide_index=True,
    )

    # ---- Apply ----
    if st.button('✅ Применить наценку', type='primary'):
        updates = []
        for p in affected_products:
            update = {
                'id': p['id'],
                'price_1': apply_markup_price(p['price_1_original'], percent),
            }
            if p['price_2_original'] is not None:
                update['price_2'] = apply_markup_price(
                    p['price_2_original'], percent
                )
            updates.append(update)

        backend.batch_update_prices(updates)
        backend.append_markup_log({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'scope_type': scope_type,
            'scope_id': scope_id,
            'percent': percent,
            'affected_count': len(affected_products),
        })

        st.success(
            f'Наценка {percent:+.1f}% применена к {len(affected_products)} '
            f'товарам ({scope_label})'
        )
        st.cache_resource.clear()
        st.rerun()

elif percent == 0:
    st.info('Введите процент наценки для предпросмотра')
else:
    st.info('Нет видимых товаров в выбранной области')
