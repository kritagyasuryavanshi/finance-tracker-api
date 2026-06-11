# routers/ai.py
"""
AI-powered API endpoints

These connect your financial data with Gemini AI
Each endpoint = one AI feature
"""

from fastapi import APIRouter, HTTPException, Depends
# APIRouter    = creates grouped routes
# HTTPException = return error responses
# Depends      = dependency injection (for DB)

from sqlalchemy.orm import Session
# Session = database connection type

from pydantic import BaseModel
# BaseModel = for defining request/response shapes

from typing import List, Optional
# For type hints

import database
# Our database operations

from db import get_db
# Function to get DB connection

from services.ai_service import (
    get_financial_insights,
    chat_with_ai,
    get_spending_advice
)
# Import our 3 AI functions


# ─────────────────────────────────────
# CREATE ROUTER
# ─────────────────────────────────────
router = APIRouter(
    prefix="/ai",
    # ↑ All routes start with /ai
    # /ai/insights, /ai/chat, /ai/advice
    
    tags=["🤖 AI Features"]
    # ↑ Groups in Swagger docs
)


# ─────────────────────────────────────
# REQUEST/RESPONSE MODELS
# ─────────────────────────────────────

class ChatRequest(BaseModel):
    """
    What frontend sends to /ai/chat
    """
    message: str
    # ↑ The user's question
    # e.g. "Where am I overspending?"
    
    chat_history: Optional[List[dict]] = []
    # ↑ Previous messages for AI memory
    # Optional = not required
    # Default = empty list


class AdviceRequest(BaseModel):
    """
    What frontend sends to /ai/advice
    """
    category: str
    # ↑ e.g. "Food", "Transport"
    
    amount: float
    # ↑ How much spent in that category


class AIResponse(BaseModel):
    """
    What ALL AI endpoints return
    Consistent response shape
    """
    response: str
    # ↑ The AI's text response
    
    success: bool = True
    # ↑ Did it work? Default True


# ─────────────────────────────────────
# ENDPOINT 1: GET /ai/insights
# ─────────────────────────────────────
@router.get("/insights", response_model=AIResponse)
async def get_insights(
    db: Session = Depends(get_db)
    # ↑ Depends(get_db) = FastAPI automatically
    #   creates a DB session and passes it here
    #   We don't manually create DB connections
    #   FastAPI handles it for us
):
    """
    Analyze ALL transactions with AI
    
    HOW IT WORKS:
    1. Get all transactions from DB
    2. Get financial summary from DB
    3. Send both to Gemini
    4. Return Gemini's analysis
    
    FRONTEND CALLS:
    GET /ai/insights
    No request body needed
    """
    try:
        # Step 1: Get data from database
        transactions = database.get_all_transactions(db)
        summary = database.get_summary(db)
        
        # Step 2: Handle empty data case
        if not transactions:
            return AIResponse(
                response="📊 Add some transactions first! I need data to analyze your finances.",
                success=True
            )
            # Return helpful message instead of error
            # Better user experience
        
        # Step 3: Get AI analysis
        insights = get_financial_insights(transactions, summary)
        # This calls Gemini API (takes 1-3 seconds)
        
        # Step 4: Return to frontend
        return AIResponse(response=insights)
    
    except Exception as e:
        # Catch ANY error (network, API, etc)
        raise HTTPException(
            status_code=500,
            detail=f"AI analysis failed: {str(e)}"
        )


# ─────────────────────────────────────
# ENDPOINT 2: POST /ai/chat
# ─────────────────────────────────────
@router.post("/chat", response_model=AIResponse)
async def chat(
    request: ChatRequest,
    # ↑ FastAPI reads request body
    #   validates against ChatRequest model
    #   passes as this parameter
    
    db: Session = Depends(get_db)
):
    """
    Chat with AI about your finances
    
    FRONTEND SENDS:
    {
        "message": "Where am I overspending?",
        "chat_history": [
            {"role": "user", "content": "previous question"},
            {"role": "assistant", "content": "previous answer"}
        ]
    }
    
    RETURNS:
    {
        "response": "You're overspending on...",
        "success": true
    }
    """
    try:
        # Get financial data as context for AI
        transactions = database.get_all_transactions(db)
        summary = database.get_summary(db)
        
        # Call AI chat function
        response = chat_with_ai(
            user_message=request.message,
            transactions=transactions,
            summary=summary,
            chat_history=request.chat_history
        )
        
        return AIResponse(response=response)
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI chat failed: {str(e)}"
        )


# ─────────────────────────────────────
# ENDPOINT 3: POST /ai/advice
# ─────────────────────────────────────
@router.post("/advice", response_model=AIResponse)
async def get_advice(
    request: AdviceRequest,
    db: Session = Depends(get_db)
):
    """
    Get AI advice for specific spending category
    
    FRONTEND SENDS:
    {
        "category": "Food",
        "amount": 500
    }
    
    RETURNS:
    {
        "response": "Your food spending is...",
        "success": true
    }
    """
    try:
        # Get income for percentage calculation
        summary = database.get_summary(db)
        
        # Get category-specific advice
        advice = get_spending_advice(
            category=request.category,
            amount=request.amount,
            total_income=summary['total_income']
        )
        
        return AIResponse(response=advice)
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI advice failed: {str(e)}"
        )