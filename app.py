import os
import sys

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Page config MUST be the first st command
st.set_page_config(
    page_title='DWG Price Admin',
    page_icon='☕',
    layout='wide',
    initial_sidebar_state='expanded',
)


def check_config() -> bool:
    sheet_id = os.getenv('PRICE_LIST_SHEET_ID', '')
    creds_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY_PATH', '')
    if not sheet_id or not creds_path:
        st.error(
            'Не настроены переменные окружения. '
            'Создайте `.env` файл с PRICE_LIST_SHEET_ID и '
            'GOOGLE_SERVICE_ACCOUNT_KEY_PATH.'
        )
        st.code(
            'PRICE_LIST_SHEET_ID=your-sheet-id\n'
            'GOOGLE_SERVICE_ACCOUNT_KEY_PATH=path/to/service-account-key.json'
        )
        return False
    if not os.path.exists(creds_path):
        st.error(f'Файл ключа сервисного аккаунта не найден: {creds_path}')
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
