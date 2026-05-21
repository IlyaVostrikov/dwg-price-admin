import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from sheets import SheetsBackend


@st.cache_resource
def get_backend() -> SheetsBackend:
    return SheetsBackend(
        sheet_id=os.getenv('PRICE_LIST_SHEET_ID', ''),
        credentials_path=os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY_PATH', ''),
    )


st.title('Каталог товаров')

backend = get_backend()

# ---- Load data ----
sections = backend.get_sections()
brands = backend.get_brands()
section_map = {s['id']: s for s in sections}
brand_map = {b['id']: b for b in brands}
brand_section_map: dict[str, str] = {b['id']: b['section_id'] for b in brands}

# ---- Filters ----
col1, col2, col3 = st.columns(3)
with col1:
    section_options = {'all': 'Все секции'} | {
        s['id']: f'{s["icon"]} {s["title_ru"]}' for s in sections
    }
    selected_section = st.selectbox(
        'Секция', options=list(section_options.keys()),
        format_func=lambda k: section_options[k],
    )
with col2:
    if selected_section == 'all':
        brand_opts = {b['id']: b['title_ru'] for b in brands}
    else:
        brand_opts = {
            b['id']: b['title_ru']
            for b in brands if b['section_id'] == selected_section
        }
    brand_options = {'all': 'Все бренды'} | brand_opts
    selected_brand = st.selectbox(
        'Бренд', options=list(brand_options.keys()),
        format_func=lambda k: brand_options[k],
    )
with col3:
    search_query = st.text_input('Поиск по названию', placeholder='Введите текст...')

# ---- Load products ----
brand_filter = None if selected_brand == 'all' else selected_brand
search_filter = search_query if search_query else None

products = backend.get_products(
    brand_id=brand_filter, search=search_filter,
)

# Filter by section if brand is not selected
if selected_section != 'all' and selected_brand == 'all':
    products = [
        p for p in products
        if brand_section_map.get(p['brand_id']) == selected_section
    ]

st.caption(f'Найдено: {len(products)} позиций')

# ---- Build display table ----
if products:
    # Build rows for st.data_editor
    rows_data = []
    for p in products:
        brand = brand_map.get(p['brand_id'], {})
        section = section_map.get(brand_section_map.get(p['brand_id'], ''), {})
        row = {
            'ID': p['id'],
            'Секция': section.get('title_ru', ''),
            'Бренд': brand.get('title_ru', ''),
            'Название': p['name_ru'],
            'Цена 1 (руб)': p['price_1'] / 100 if p['price_1'] else 0,
            'Видимый': p['visible'],
        }
        if brand.get('has_dual_pricing'):
            row['Цена 2 (руб)'] = (
                p['price_2'] / 100 if p['price_2'] else 0.0
            )
        rows_data.append(row)

    # Column config
    column_config = {
        'ID': st.column_config.NumberColumn('ID', disabled=True),
        'Секция': st.column_config.TextColumn('Секция', disabled=True),
        'Бренд': st.column_config.TextColumn('Бренд', disabled=True),
        'Название': st.column_config.TextColumn('Название', disabled=True),
        'Цена 1 (руб)': st.column_config.NumberColumn(
            'Цена 1 (руб)', min_value=0, step=1, format='%d',
        ),
        'Видимый': st.column_config.CheckboxColumn('Видимый'),
    }
    if 'Цена 2 (руб)' in rows_data[0] if rows_data else False:
        column_config['Цена 2 (руб)'] = st.column_config.NumberColumn(
            'Цена 2 (руб)', min_value=0, step=1, format='%d',
        )

    edited = st.data_editor(
        rows_data,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        num_rows='fixed',
        key='catalog_editor',
    )

    # Save button
    if st.button('💾 Сохранить изменения', type='primary'):
        saved = 0
        for i, row in enumerate(edited):
            orig = rows_data[i]
            pid = orig['ID']
            changes = {}

            price1_new = int(row['Цена 1 (руб)'] * 100)
            if price1_new != products[i]['price_1']:
                changes['price_1'] = price1_new

            if 'Цена 2 (руб)' in row:
                price2_val = row['Цена 2 (руб)']
                price2_new = int(price2_val * 100) if price2_val else None
                if price2_new != products[i]['price_2']:
                    changes['price_2'] = price2_new

            if row['Видимый'] != orig['Видимый']:
                changes['visible'] = row['Видимый']

            if changes:
                backend.update_product(pid, changes)
                saved += 1

        if saved > 0:
            st.success(f'Сохранено {saved} изменений')
            st.cache_resource.clear()
            st.rerun()
        else:
            st.info('Нет изменений для сохранения')
else:
    st.info('Нет товаров, соответствующих фильтрам')
