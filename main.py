# main.py
"""
Finance Tracker API
Run: uvicorn main:app --reload
Docs: http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import transactions


# ─────────────────────────────────────────
# Create FastAPI App
# ─────────────────────────────────────────
app = FastAPI(
    title="💰 Finance Tracker API",
    description="""
Track your personal finances via REST API.

## What you can do:

* **Create** income and expense transactions
* **Read** all transactions or filter by type
* **Delete** transactions
* **Summary** get total income, expenses and balance

## Built by
Kritagya Suryavanshi | Full Stack AI Engineer
    """,
    version="1.0.0"
)


# ─────────────────────────────────────────
# CORS Middleware
# This lets your Next.js frontend call this API
# ─────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production: specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────
# Include Routers
# ─────────────────────────────────────────
app.include_router(transactions.router)


# ─────────────────────────────────────────
# Root Endpoint
# ─────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    """API info and health check"""
    return {
        "name": "Finance Tracker API",
        "version": "1.0.0",
        "status": "✅ running",
        "docs": "http://localhost:8000/docs",
        "endpoints": {
            "all transactions": "GET /transactions",
            "create transaction": "POST /transactions",
            "get summary": "GET  /transactions/summary",
            "get one": "GET /transactions/{id}",
            "delete": "DELETE /transactions/{id}"
        }
    }


@app.get("/health", tags=["Health"])
async def health():
    """Simple health check for deployment"""
    return {"status": "healthy"}