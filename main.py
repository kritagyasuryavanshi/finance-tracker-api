# main.py
"""
Finance Tracker API
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import transactions
from db import init_db
from routers import ai  


# ─────────────────────────────────────
# LIFESPAN: Startup & Shutdown
# ─────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup (gracefully handle errors)"""
    try:
        init_db()
        print("✅ Database initialized successfully")
    except Exception as e:
        # Don't fail app startup if DB is unavailable
        print(f"⚠️ Database initialization failed: {str(e)[:100]}")
        print("⚠️ App will run without database - will reconnect on next request")
    
    yield
    
    print("👋 Application shutdown")


# ─────────────────────────────────────
# CREATE APP WITH LIFESPAN
# ─────────────────────────────────────
app = FastAPI(
    title="💰 Finance Tracker API",
    description="Track your personal finances via REST API",
    version="1.0.0",
    lifespan=lifespan
)


# ─────────────────────────────────────
# CORS MIDDLEWARE
# ─────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────
# INCLUDE ROUTERS
# ─────────────────────────────────────
app.include_router(transactions.router)
app.include_router(ai.router)


# ─────────────────────────────────────
# HEALTH CHECK ENDPOINTS
# ─────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    """API info and health check"""
    return {
        "name": "Finance Tracker API",
        "version": "1.0.0",
        "status": "✅ running",
        "docs": "http://localhost:8000/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    """Simple health check"""
    return {"status": "healthy"}