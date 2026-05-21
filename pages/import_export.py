import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from generator import generate_html
from parser import import_to_db
from db import SqliteBackend


@st.cache_resource
def get_backend() -> SqliteBackend:
    return SqliteBackend(os.getenv('DB_PATH', 'pricelist.db'))


st.title('Импорт / Экспорт')

backend = get_backend()

tab1, tab2 = st.tabs(['Импорт из HTML', 'Экспорт в HTML'])

with tab1:
    st.subheader('Импорт прайс-листа в базу данных')

    html_path = st.text_input(
        'Путь к HTML-файлу',
        value=os.getenv('SOURCE_HTML_PATH', 'Единый прайс.html'),
    )

    if not os.path.exists(html_path):
        st.warning(f'Файл не найден: {html_path}')
    else:
        st.info(
            f'Файл найден: {html_path} '
            f'({os.path.getsize(html_path):,} байт)'
        )

    st.warning(
        '⚠️ Импорт **перезапишет** все данные в базе данных '
        '(секции, бренды, товары). Текущие наценки будут потеряны.'
    )

    if st.button('📥 Импортировать в базу данных', type='primary'):
        if not os.path.exists(html_path):
            st.error(f'Файл не найден: {html_path}')
        else:
            with st.spinner('Парсинг HTML и запись в базу данных...'):
                try:
                    result = import_to_db(html_path, backend)
                    st.success(
                        f'Импорт завершён!\n\n'
                        f'- Секций: {result["sections_created"]}\n'
                        f'- Брендов: {result["brands_created"]}\n'
                        f'- Товаров: {result["products_created"]}'
                    )
                    if result['errors']:
                        st.warning(f'Ошибки: {result["errors"]}')
                    st.cache_resource.clear()
                except Exception as e:
                    st.error(f'Ошибка импорта: {e}')

with tab2:
    st.subheader('Генерация HTML-прайс-листа')

    st.markdown(
        'Генерирует HTML-файл на основе данных из Google Sheets. '
        'Включаются только **видимые** секции, бренды и товары.'
    )

    # Show what will be included
    sections = backend.get_sections()
    brands = backend.get_brands()
    products = backend.get_products(visible_only=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        visible_sections = [s for s in sections if s['visible']]
        st.metric('Видимых секций', len(visible_sections))
    with col2:
        visible_brands = [b for b in brands if b['visible']]
        st.metric('Видимых брендов', len(visible_brands))
    with col3:
        st.metric('Видимых товаров', len(products))

    if st.button('🖨️ Сгенерировать HTML', type='primary'):
        with st.spinner('Генерация HTML...'):
            try:
                html = generate_html(backend)
                date_str = datetime.now().strftime('%Y-%m-%d')
                filename = f'Единый прайс ({date_str}).html'

                st.success(
                    f'HTML сгенерирован ({len(html):,} символов, '
                    f'{len(html.splitlines())} строк)'
                )
                st.download_button(
                    label='📄 Скачать HTML',
                    data=html,
                    file_name=filename,
                    mime='text/html',
                )

                # Preview
                with st.expander('Предпросмотр HTML (первые 80 строк)'):
                    preview_lines = html.split('\n')[:80]
                    st.code('\n'.join(preview_lines), language='html')
            except Exception as e:
                st.error(f'Ошибка генерации: {e}')
