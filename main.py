# main.py
"""
Finance Tracker API
"""

import logging
from contextlib import asynccontextmanager

import config  # noqa: F401  (loads env, API key aliases and logging first)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import init_db
from routers import ai, auth, transactions

logger = logging.getLogger(__name__)


# ─────────────────────────────────────
# LIFESPAN: Startup & Shutdown
# ─────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup; keep serving (health checks) if the DB is down."""
    try:
        init_db()
        logger.info("Database initialized")
    except Exception:
        logger.exception("Database initialization failed; requests that need the DB will error until it is reachable")
    yield


app = FastAPI(
    title="Finance Tracker API",
    description="AI-powered personal finance API: transactions, RAG, LangGraph and CrewAI analyses",
    version="1.1.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────
# CORS
# Auth uses Bearer tokens (not cookies), so credentials are not needed.
# Set ALLOWED_ORIGINS to your frontend URL in production.
# ─────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(transactions.router)
app.include_router(ai.router)
app.include_router(auth.router)


@app.get("/", tags=["Health"])
def root():
    """API info"""
    return {"name": "Finance Tracker API", "version": "1.1.0", "status": "running", "docs": "/docs"}


@app.get("/health", tags=["Health"])
def health():
    """Lightweight health check, also used by the frontend to wake the server"""
    return {"status": "healthy"}
