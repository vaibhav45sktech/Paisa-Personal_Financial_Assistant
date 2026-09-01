"""WSGI entrypoint for production servers (gunicorn, Vercel's Python runtime).

Vercel's zero-config Python detection looks for a top-level `app` variable in
one of a fixed set of filenames (app.py, index.py, server.py, main.py,
wsgi.py, asgi.py) — `run.py` is not one of them, so this file exists purely
to be found. Local development still uses `run.py` / `flask run`.
"""
from app import create_app

app = create_app()
