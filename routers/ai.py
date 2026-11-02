# routers/ai.py
"""
AI endpoints: insights, chat, advice, document RAG, LangGraph and CrewAI analyses.

Design notes:
- Endpoints are plain `def`, so FastAPI runs them in a worker thread. A slow LLM call
  (CrewAI takes ~60s) no longer blocks logins and other requests.
- The heavy AI libraries (LangChain, LangGraph, CrewAI, Chroma) are imported inside
  each endpoint, so the server starts fast and only pays their memory cost when used.
- Every endpoint requires a logged-in user and only touches that user's data.
- Errors are logged server-side; clients get a short, safe message.
"""

import logging
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import database
from db import get_db
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

router = APIRouter(prefix="/ai", tags=["AI Features"])


# ─────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ─────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    # Earlier turns of the conversation, NOT including `message`
    chat_history: Optional[List[ChatMessage]] = []


class AdviceRequest(BaseModel):
    category: str
    amount: float


class AIResponse(BaseModel):
    response: str
    success: bool = True


class DeepAnalysisResponse(BaseModel):
    final_output: str
    financial_health: str
    alert_message: str
    summary: dict
    error: Optional[str] = None


class CrewAnalysisResponse(BaseModel):
    report: str
    success: bool = True


class DocumentQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    use_agent: bool = False


class DocumentUploadResponse(BaseModel):
    success: bool
    message: str
    documents_loaded: int


class DocumentQueryResponse(BaseModel):
    answer: str
    sources: Optional[List[str]] = None
    from_agent: bool = False


def _ai_error(action: str) -> HTTPException:
    logger.exception("%s failed", action)
    return HTTPException(status_code=502, detail=f"{action} failed. The AI service may be busy; please try again.")


# ─────────────────────────────────────
# INSIGHTS, CHAT, ADVICE (Gemini)
# ─────────────────────────────────────

@router.get("/insights", response_model=AIResponse)
def get_insights(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """AI summary of the current user's spending."""
    transactions = database.get_all_transactions(db, user_id=current_user["id"])
    if not transactions:
        return AIResponse(response="Add a few transactions first, then I can analyse your finances.")

    summary = database.get_summary(db, user_id=current_user["id"])
    try:
        from services.ai_service import get_financial_insights

        return AIResponse(response=get_financial_insights(transactions, summary))
    except Exception:
        raise _ai_error("AI insights")


@router.post("/chat", response_model=AIResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Chat about the current user's finances, with conversation history."""
    transactions = database.get_all_transactions(db, user_id=current_user["id"])
    summary = database.get_summary(db, user_id=current_user["id"])

    # Older clients sent the new message inside the history too; drop that duplicate
    history = [m.model_dump() for m in (request.chat_history or [])]
    if history and history[-1]["role"] == "user" and history[-1]["content"] == request.message:
        history = history[:-1]

    try:
        from services.ai_service import chat_with_ai

        return AIResponse(
            response=chat_with_ai(
                user_message=request.message,
                transactions=transactions,
                summary=summary,
                chat_history=history,
            )
        )
    except Exception:
        raise _ai_error("AI chat")


@router.post("/advice", response_model=AIResponse)
def get_advice(request: AdviceRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Advice on spending a given amount in one category."""
    summary = database.get_summary(db, user_id=current_user["id"])
    try:
        from services.ai_service import get_spending_advice

        return AIResponse(
            response=get_spending_advice(
                category=request.category,
                amount=request.amount,
                total_income=summary["total_income"],
            )
        )
    except Exception:
        raise _ai_error("AI advice")


# ─────────────────────────────────────
# DOCUMENTS (RAG over the user's own uploaded CSV)
# ─────────────────────────────────────

@router.post("/upload", response_model=DocumentUploadResponse)
def upload_document(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Upload a CSV statement; it replaces this user's previously uploaded document."""
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    contents = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 5 MB.")
    if not contents.strip():
        raise HTTPException(status_code=400, detail="The file is empty.")

    tmp_path = None
    try:
        from services.langchain_service import index_user_csv

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        count = index_user_csv(current_user["id"], tmp_path, file.filename)
        if count == 0:
            return DocumentUploadResponse(success=False, message="No rows found in the CSV.", documents_loaded=0)
        return DocumentUploadResponse(
            success=True, message=f"Loaded {count} rows from {file.filename}", documents_loaded=count
        )
    except Exception:
        logger.exception("Upload failed")
        return DocumentUploadResponse(
            success=False, message="Could not process this CSV. Check it has a header row.", documents_loaded=0
        )
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


@router.post("/query-documents", response_model=DocumentQueryResponse)
def query_uploaded_documents(request: DocumentQueryRequest, current_user: dict = Depends(get_current_user)):
    """Ask a question about the user's uploaded CSV, via RAG or the ReAct agent."""
    try:
        from services.langchain_service import query_documents, query_with_agent

        if request.use_agent:
            return DocumentQueryResponse(answer=query_with_agent(current_user["id"], request.question), from_agent=True)

        result = query_documents(current_user["id"], request.question)
        return DocumentQueryResponse(answer=result["answer"], sources=result["sources"])
    except Exception:
        raise _ai_error("Document question")


@router.post("/hybrid-search", response_model=DocumentQueryResponse)
def hybrid_search_documents(request: DocumentQueryRequest, current_user: dict = Depends(get_current_user)):
    """Semantic + keyword search over the user's uploaded CSV."""
    try:
        from services.langchain_service import hybrid_search

        results = hybrid_search(current_user["id"], request.question, k=3)
        return DocumentQueryResponse(answer="\n".join(results) or "No results found", sources=[])
    except Exception:
        raise _ai_error("Search")


# ─────────────────────────────────────
# AGENTS
# ─────────────────────────────────────

@router.get("/deep-analysis", response_model=DeepAnalysisResponse)
def deep_analysis(current_user: dict = Depends(get_current_user)):
    """LangGraph state-machine analysis of the user's finances."""
    try:
        from services.finance_agent import run_finance_analysis

        result = run_finance_analysis(current_user["id"])
        return DeepAnalysisResponse(
            final_output=result["final_output"],
            financial_health=result["financial_health"],
            alert_message=result["alert_message"],
            summary=result["summary"],
            error=result.get("error"),
        )
    except Exception:
        raise _ai_error("Deep analysis")


@router.get("/crew-analysis", response_model=CrewAnalysisResponse)
def crew_analysis(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """CrewAI three-agent analysis (analyst, advisor, report writer)."""
    transactions = database.get_all_transactions(db, user_id=current_user["id"])
    summary = database.get_summary(db, user_id=current_user["id"])
    try:
        from services.finance_crew import run_finance_crew

        return CrewAnalysisResponse(
            report=run_finance_crew(transactions=transactions, summary=summary, user_id=current_user["id"])
        )
    except Exception:
        raise _ai_error("Crew analysis")
