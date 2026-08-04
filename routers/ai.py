# routers/ai.py
"""
AI-powered API endpoints

These connect your financial data with Gemini AI
Each endpoint = one AI feature
"""

from fastapi import APIRouter, HTTPException, Depends , File, UploadFile
# APIRouter    = creates grouped routes
# HTTPException = return error responses
# Depends      = dependency injection (for DB)
from services.finance_agent import run_finance_analysis
from sqlalchemy.orm import Session
# Session = database connection type

from pydantic import BaseModel, Field
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
from routers.auth import get_current_user

import shutil
from pathlib import Path
import tempfile

from services.langchain_service import (
    load_and_process_csv,
    create_vector_store,
    query_documents,
    query_with_agent,
    hybrid_search
)




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


class DeepAnalysisResponse(BaseModel):
    """Response from LangGraph agent"""
    final_output: str
    financial_health: str
    alert_message: str
    summary: dict
    error: Optional[str] = None




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
    

    # ─────────────────────────────────────────────────────
# NEW REQUEST MODELS
# ─────────────────────────────────────────────────────

class DocumentQueryRequest(BaseModel):
    """
    User asking question about uploaded documents
    """
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000
    )
    use_agent: bool = False
    # ↑ Use multi-agent system if True


class DocumentUploadResponse(BaseModel):
    """
    Response after uploading document
    """
    success: bool
    message: str
    documents_loaded: int


class DocumentQueryResponse(BaseModel):
    """
    Response to document query
    """
    answer: str
    sources: Optional[List[str]] = None
    from_agent: bool = False


# ─────────────────────────────────────────────────────
# ENDPOINT 1: POST /ai/upload
# Upload CSV with financial data
# ─────────────────────────────────────────────────────

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload CSV file for AI to learn from
    
    FRONTEND SENDS:
    - file: CSV file (multipart/form-data)
    
    EXAMPLE CSV:
    Date,Category,Amount,Type
    2024-01-01,Food,500,expense
    2024-01-02,Salary,5000,income
    
    RETURNS:
    {
        "success": true,
        "message": "Loaded 365 transactions",
        "documents_loaded": 365
    }
    """
    
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise ValueError("Only CSV files supported")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix='.csv'
        ) as tmp:
            # Save uploaded file to temp location
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name
        
        # Load and process CSV
        documents = load_and_process_csv(tmp_path)
        
        if not documents:
            return DocumentUploadResponse(
                success=False,
                message="No data found in CSV",
                documents_loaded=0
            )
        
        # Create vector store
        create_vector_store(documents)
        
        # Clean up temp file
        Path(tmp_path).unlink()
        
        return DocumentUploadResponse(
            success=True,
            message=f"Successfully loaded {len(documents)} transactions",
            documents_loaded=len(documents)
        )
    
    except Exception as e:
        return DocumentUploadResponse(
            success=False,
            message=f"Upload failed: {str(e)}",
            documents_loaded=0
        )


# ─────────────────────────────────────────────────────
# ENDPOINT 2: POST /ai/query-documents
# Ask questions about uploaded documents
# ─────────────────────────────────────────────────────

@router.post("/query-documents", response_model=DocumentQueryResponse)
async def query_uploaded_documents(request: DocumentQueryRequest):
    """
    Ask questions about uploaded financial data
    
    FRONTEND SENDS:
    {
        "question": "What's my biggest spending month?",
        "use_agent": true
    }
    
    RETURNS:
    {
        "answer": "Your biggest spending was July...",
        "sources": ["2024-07-01, Food, 500", ...],
        "from_agent": true
    }
    """
    
    try:
        if request.use_agent:
            # Use multi-agent system
            # Better for complex questions
            answer = query_with_agent(request.question)
            
            return DocumentQueryResponse(
                answer=answer,
                from_agent=True
            )
        
        else:
            # Use simple RAG
            # Faster for simple questions
            result = query_documents(request.question)
            
            return DocumentQueryResponse(
                answer=result["answer"],
                sources=result["sources"],
                from_agent=False
            )
    
    except Exception as e:
        return DocumentQueryResponse(
            answer=f"Error: {str(e)}",
            from_agent=False
        )


# ─────────────────────────────────────────────────────
# ENDPOINT 3: POST /ai/hybrid-search
# Advanced search with multiple strategies
# ─────────────────────────────────────────────────────

@router.post("/hybrid-search", response_model=DocumentQueryResponse)
async def hybrid_search_documents(request: DocumentQueryRequest):
    """
    Search with hybrid approach:
    - Semantic similarity
    - Keyword matching
    - Re-ranking
    
    Best for precise answers
    """
    
    try:
        results = hybrid_search(request.question, k=3)
        
        # Format results
        answer = "\n".join([
            doc.page_content if hasattr(doc, 'page_content') else str(doc)
            for doc in results
        ])
        
        return DocumentQueryResponse(
            answer=answer if answer else "No results found",
            sources=[]
        )
    
    except Exception as e:
        return DocumentQueryResponse(
            answer=f"Error: {str(e)}"
        )


@router.get("/deep-analysis", response_model=DeepAnalysisResponse)
async def deep_analysis(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
    # ↑ Protected! Must be logged in
):
    """
    Run complete LangGraph financial intelligence analysis
    
    Runs a multi-node AI graph:
    1. Fetches user's transactions
    2. Analyzes spending patterns with AI
    3. Determines financial health
    4. Generates personalized report
    5. Returns formatted output
    
    Takes 5-15 seconds (multiple AI calls)
    Much more detailed than /ai/insights
    """
    
    try:
        result = run_finance_analysis(current_user["id"])
        # ↑ Pass user_id to graph
        #   Graph handles everything else!
        
        return DeepAnalysisResponse(
            final_output=result["final_output"],
            financial_health=result["financial_health"],
            alert_message=result["alert_message"],
            summary=result["summary"],
            error=result.get("error")
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )
