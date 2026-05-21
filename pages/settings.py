import json
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from db import SqliteBackend


@st.cache_resource
def get_backend() -> SqliteBackend:
    return SqliteBackend(os.getenv('DB_PATH', 'pricelist.db'))


def brand_map_name(bid: str, brands: list[dict]) -> str:
    for b in brands:
        if b['id'] == bid:
            return b['title_ru']
    return bid


st.title('Управление видимостью')

backend = get_backend()

sections = backend.get_sections()
brands = backend.get_brands()
section_map = {s['id']: s for s in sections}

tab1, tab2 = st.tabs(['Секции и бренды', 'Добавить / Удалить бренд'])

with tab1:
    st.subheader('Видимость секций')

    for s in sections:
        col1, col2 = st.columns([0.1, 0.9])
        with col1:
            new_visible = st.toggle(
                'sec_' + s['id'],
                value=s['visible'],
                label_visibility='collapsed',
            )
        with col2:
            st.write(f'{s["icon"]} **{s["title_ru"]}**')
        if new_visible != s['visible']:
            backend.toggle_section_visibility(s['id'], new_visible)
            st.cache_resource.clear()
            st.rerun()

    st.divider()
    st.subheader('Видимость брендов')

    for s in sections:
        section_brands = [b for b in brands if b['section_id'] == s['id']]
        if not section_brands:
            continue
        st.markdown(f'**{s["icon"]} {s["title_ru"]}**')
        for b in section_brands:
            col1, col2, col3 = st.columns([0.1, 0.7, 0.2])
            with col1:
                new_visible = st.toggle(
                    'br_' + b['id'],
                    value=b['visible'],
                    label_visibility='collapsed',
                )
            with col2:
                st.write(b['title_ru'])
                if b['subtitle_ru']:
                    st.caption(b['subtitle_ru'])
            with col3:
                products = backend.get_products(brand_id=b['id'])
                st.caption(f'{len(products)} поз.')
            if new_visible != b['visible']:
                backend.toggle_brand_visibility(b['id'], new_visible)
                st.cache_resource.clear()
                st.rerun()

with tab2:
    st.subheader('Добавить бренд')

    with st.form('add_brand_form'):
        brand_id = st.text_input('ID бренда (лат. slug)', placeholder='my-brand')
        section_id = st.selectbox(
            'Секция',
            options=[s['id'] for s in sections],
            format_func=lambda k: f'{section_map[k]["icon"]} {section_map[k]["title_ru"]}',
        )
        title = st.text_input('Название бренда')
        subtitle = st.text_input('Подзаголовок (опционально)')
        has_dual = st.checkbox('Две цены (с арендой / без аренды)')

        col_h, col_p = st.columns(2)
        with col_h:
            headers_raw = st.text_area(
                'Заголовки колонок (по одному на строку)',
                value='НАИМЕНОВАНИЕ',
                help='Первая строка — всегда название товара. '
                     'Для цен напишите «Цена, руб» или «Цена с арендой, руб».',
            )
        with col_p:
            price_indices_raw = st.text_input(
                'Индексы ценовых колонок (считая от 0, через запятую)',
                value='1' if not has_dual else '1, 2',
                help='Укажите индексы колонок с ценами. Первая колонка (НАИМЕНОВАНИЕ) = 0.',
            )

        submitted = st.form_submit_button('Добавить бренд')
        if submitted:
            if not brand_id or not title:
                st.error('ID и название обязательны')
            else:
                headers = [
                    h.strip() for h in headers_raw.strip().split('\n') if h.strip()
                ]
                try:
                    price_indices = [
                        int(x.strip())
                        for x in price_indices_raw.split(',') if x.strip()
                    ]
                except ValueError:
                    st.error('Индексы цен должны быть числами через запятую')
                    st.stop()

                brand = {
                    'id': brand_id,
                    'section_id': section_id,
                    'title_ru': title,
                    'subtitle_ru': subtitle,
                    'sort_order': 99,
                    'visible': True,
                    'has_dual_pricing': len(price_indices) >= 2,
                    'column_headers': headers,
                    'price_col_indices': price_indices,
                }
                backend.add_brand(brand)
                st.success(f'Бренд «{title}» добавлен')
                st.cache_resource.clear()
                st.rerun()

    st.divider()
    st.subheader('Удалить бренд')

    brand_to_delete = st.selectbox(
        'Выберите бренд для удаления',
        options=[b['id'] for b in brands],
        format_func=lambda k: brand_map_name(k, brands),
    )
    if st.button('🗑️ Удалить бренд', type='secondary'):
        brand_name = brand_map_name(brand_to_delete, brands)
        st.warning(f'Вы уверены, что хотите удалить бренд «{brand_name}»?')
        if st.button('✅ Подтвердить удаление', type='primary'):
            backend.delete_brand(brand_to_delete)
            st.success(f'Бренд «{brand_name}» удалён')
            st.cache_resource.clear()
            st.rerun()
