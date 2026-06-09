import streamlit as st

from backend_factory import get_backend as _get_backend
from db import SqliteBackend
from sheets import SheetsBackend


@st.cache_resource
def get_backend() -> SqliteBackend | SheetsBackend:
    return _get_backend()
