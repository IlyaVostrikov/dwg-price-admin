import os
import sys

import streamlit as st
# Page config MUST be the first st command
st.set_page_config(
    page_title='DWG Price Admin',
    page_icon='☕',
    layout='wide',
    initial_sidebar_state='expanded',
)


def check_auth() -> bool:
    """Return True if the user is authenticated."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    admin_password = st.secrets.get('ADMIN_PASSWORD', os.getenv('ADMIN_PASSWORD', ''))
    if not admin_password:
        st.error(
            'ADMIN_PASSWORD не задан. '
            'Добавьте его в .streamlit/secrets.toml или в переменные окружения.'
        )
        st.stop()

    st.markdown('## ☕ DWG Price Admin')
    st.markdown('Введите пароль для доступа к админ-панели.')

    password = st.text_input('Пароль', type='password', key='auth_password')
    if st.button('Войти', type='primary'):
        if password == admin_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error('Неверный пароль')

    st.stop()


def check_config() -> bool:
    db_path = os.getenv('DB_PATH', 'pricelist.db')
    if not os.path.exists(db_path):
        st.error(
            'База данных не найдена. '
            'Сначала запустите `uv run python init_db.py` для импорта прайс-листа.'
        )
        return False
    return True


if check_auth() and check_config():
    pages = st.navigation([
        st.Page('pages/catalog.py', title='Каталог', icon='📋'),
        st.Page('pages/markup.py', title='Наценки', icon='💰'),
        st.Page('pages/settings.py', title='Видимость', icon='👁️'),
        st.Page('pages/import_export.py', title='Импорт / Экспорт', icon='📦'),
    ])
    pages.run()
else:
    st.stop()
