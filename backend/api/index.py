"""
Vercel Python serverless entry point for the FastAPI application.
Vercel discovers `app` from this module and serves it via ASGI.

Deploy this backend by pointing Vercel's root directory to `backend/`
and setting the environment variables listed in vercel.json.
"""
import sys
import os

# Add the backend root to sys.path.
# This file lives at  backend/api/index.py
# Backend root is     backend/
_backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

from app.main import app  # noqa: E402 — must be after sys.path setup

# Vercel imports `app` from this module — nothing else needed.
