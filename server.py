"""Flask server for public price list — reads DB and renders HTML."""

import os

from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

from generator import generate_html
from backend_factory import get_backend as _get_backend

app = Flask(__name__)


def get_backend():
    backend = _get_backend()
    # SqliteBackend supports read_only mode for extra safety on Vercel
    if hasattr(backend, 'read_only'):
        backend.read_only = True
    return backend


# Cache HTML in memory (module-level, lives for serverless function duration)
_html_cache: str | None = None


def get_html() -> str:
    global _html_cache
    if _html_cache is None:
        backend = get_backend()
        _html_cache = generate_html(backend)
    return _html_cache


@app.route("/")
def price_list():
    return get_html()


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/regenerate")
def regenerate():
    token = os.getenv("REGEN_TOKEN", "")
    if token and request.args.get("token") != token:
        return {"error": "unauthorized"}, 401
    global _html_cache
    _html_cache = None
    return {"status": "regenerated", "size": len(get_html())}


# Vercel entry point
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
