"""
FastAPI application entrypoint.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

# Sales Bot Routers
from app.api.routes import router as api_router
from app.api.text_to_sql_routes import router as text_to_sql_router
from app.api.designer_routes import router as designer_router
from app.db.session import Base, engine

# Estimation Bot Routers & Lifespan Tasks
from app.routers import search, documents, chat, ingest, predict, certiq_router, knn_router, knn_predict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 1. Create/Validate PostgreSQL tables ──
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("PostgreSQL database tables created/verified ✅")
    except OperationalError as exc:
        hint = (
            "PostgreSQL is not reachable at startup. This is normal on serverless if the database is waking up (e.g. Neon) "
            "or if credentials are not yet configured. The application will attempt to connect on-demand during requests. "
            "Please verify your DATABASE_URL in Vercel project environment variables if database operations continue to fail."
        )
        logger.warning("%s Original error: %s", hint, exc)

    # ── 2. Loading FAISS index ──
    logger.info("Server starting — loading FAISS index...")
    try:
        from retrieval.index_builder import load_faiss_index
        index, chunk_ids = load_faiss_index()
        app.state.index = index
        app.state.chunk_ids = chunk_ids
        app.state.total_chunks = index.ntotal
        logger.info(f"FAISS ready — {index.ntotal} chunks indexed ✅")
    except Exception as e:
        logger.warning(f"FAISS index load warning (non-fatal): {e}")
        app.state.total_chunks = 0

    # ── 3. Initialize certiq KNN SQLite database ──
    try:
        from certiq.store import setup_knn_tables, seed_roofing_product_type
        setup_knn_tables()
        seed_roofing_product_type()
        logger.info("KNN SQLite store ready ✅")
    except Exception as e:
        logger.warning(f"KNN store init warning (non-fatal): {e}")

    logger.info("Server fully ready ✅")
    yield

    logger.info("Server shutting down cleanly")


app = FastAPI(
    title="Unified Sales & Construction AI Platform",
    description="Consolidated backend offering PostgreSQL Sales Analytics, Text-to-SQL reasoning, and FAISS/KNN Construction QA.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sales Bot routers
app.include_router(api_router)
app.include_router(text_to_sql_router)
app.include_router(designer_router)

# Construction/Estimation Bot routers
app.include_router(search.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(ingest.router)
app.include_router(predict.router)
app.include_router(certiq_router.router)
app.include_router(knn_router.router)
app.include_router(knn_predict.router)


@app.get("/")
def read_root():
    return {
        "message": "Unified Chatbot Backend API is running.",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
def health():
    total = getattr(app.state, "total_chunks", 0)
    
    # Report KNN store status
    knn_status = "unknown"
    knn_certs = 0
    try:
        from certiq.store import get_all_cert_jobs
        jobs = get_all_cert_jobs("LA")
        knn_certs = len(jobs)
        knn_status = "ready" if knn_certs > 0 else "empty"
    except Exception:
        knn_status = "unavailable"

    # Safely mask the database URL for debugging
    db_url = "unknown"
    try:
        from urllib.parse import urlparse, urlunparse
        from app.core.config import settings
        raw_url = settings.database_url
        parsed = urlparse(raw_url)
        if parsed.password:
            netloc = f"{parsed.username}:*****@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            parsed = parsed._replace(netloc=netloc)
            db_url = urlunparse(parsed)
        else:
            db_url = raw_url
    except Exception as e:
        db_url = f"error masking url: {e}"

    return {
        "status": "ok",
        "chunks_indexed": total,
        "knn_store": knn_status,
        "knn_certs": knn_certs,
        "database_url": db_url,
        "message": f"Server healthy — {total} chunks indexed | KNN store: {knn_status} ({knn_certs} certs) | DB: {db_url}"
    }
