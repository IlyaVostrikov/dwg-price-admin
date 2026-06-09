import os

import streamlit as st
# Page config MUST be the first st command
st.set_page_config(
    page_title='DWG Price Admin',
    page_icon='☕',
    layout='wide',
    initial_sidebar_state='expanded',
)


def check_config() -> bool:
    if os.getenv('BACKEND', 'sqlite') == 'sheets':
        sheet_id = os.getenv('PRICE_LIST_SHEET_ID', '')
        if not sheet_id:
            st.error('PRICE_LIST_SHEET_ID не задан. Проверьте secrets на Streamlit Cloud.')
            return False
        return True

    db_path = os.getenv('DB_PATH', 'pricelist.db')
    if not os.path.exists(db_path):
        st.error(
            'База данных не найдена. '
            'Сначала запустите `uv run python init_db.py` для импорта прайс-листа.'
        )
        return False
    return True


if check_config():
    pages = st.navigation([
        st.Page('pages/catalog.py', title='Каталог', icon='📋'),
        st.Page('pages/markup.py', title='Наценки', icon='💰'),
        st.Page('pages/settings.py', title='Видимость', icon='👁️'),
        st.Page('pages/import_export.py', title='Импорт / Экспорт', icon='📦'),
    ])
    pages.run()
else:
    st.stop()
