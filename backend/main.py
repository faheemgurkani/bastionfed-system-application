"""
ASGI entry for Vercel's Python runtime.

Vercel loads a supported root file (`main.py`, `app.py`, `index.py`, or `server.py`)
and expects a FastAPI instance named `app`. The real application lives in `app.main`.
"""

from app.main import app

__all__ = ["app"]
