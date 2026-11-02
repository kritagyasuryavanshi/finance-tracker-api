"""
RAG over a user's uploaded CSV statement.

- Each user gets a private Chroma collection (user_<id>), persisted on disk, so
  users never see each other's documents and data survives a restart.
- A new upload replaces that user's previous document.
- Totals are computed deterministically from the CSV at upload time (when the
  columns can be recognised); the LLM explains numbers, it does not add them up.
- query_with_agent runs a ReAct agent whose tools are bound to one user's store.
"""

import csv
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

import config  # noqa: F401  (API key aliases)
from config import DATA_DIR, money
from langchain_chroma import Chroma
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_classic.chains import RetrievalQA
from langchain_community.document_loaders import CSVLoader
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)
embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)


# ─────────────────────────────────────
# PER-USER STORAGE
# ─────────────────────────────────────

def _collection_name(user_id: str) -> str:
    return f"user_{user_id.replace('-', '')}"[:63]


def _stats_path(user_id: str) -> Path:
    return Path(DATA_DIR) / f"stats_{_collection_name(user_id)}.json"


def _open_store(user_id: str) -> Chroma:
    os.makedirs(DATA_DIR, exist_ok=True)
    return Chroma(
        collection_name=_collection_name(user_id),
        embedding_function=embeddings,
        persist_directory=DATA_DIR,
    )


def get_user_store(user_id: str) -> Optional[Chroma]:
    """The user's vector store, or None if they have not uploaded anything."""
    store = _open_store(user_id)
    return store if store._collection.count() > 0 else None


# ─────────────────────────────────────
# UPLOAD
# ─────────────────────────────────────

def _to_number(value: str) -> Optional[float]:
    cleaned = (value or "").replace(",", "").replace("₹", "").replace("$", "").replace("Rs", "").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        return float(cleaned)
    except ValueError:
        return None


def compute_csv_stats(file_path: str) -> Optional[Dict]:
    """
    Work out income / expense totals from common statement layouts:
    - separate Debit / Credit (or Withdrawal / Deposit) columns
    - an Amount column plus a Type column (income / expense, credit / debit)
    - a signed Amount column (negative = expense)
    Returns None when the layout is not recognised.
    """
    with open(file_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None

    cols = {c.lower().strip(): c for c in rows[0].keys() if c}

    def find(*names):
        for key, original in cols.items():
            if any(n in key for n in names):
                return original
        return None

    debit, credit = find("debit", "withdrawal"), find("credit", "deposit")
    amount, kind = find("amount", "value"), find("type")
    income = expense = 0.0

    if debit and credit:
        for r in rows:
            expense += abs(_to_number(r.get(debit)) or 0)
            income += abs(_to_number(r.get(credit)) or 0)
    elif amount and kind:
        for r in rows:
            value = abs(_to_number(r.get(amount)) or 0)
            label = (r.get(kind) or "").lower()
            if any(w in label for w in ("income", "credit", "deposit", "salary")):
                income += value
            else:
                expense += value
    elif amount:
        for r in rows:
            value = _to_number(r.get(amount)) or 0
            if value >= 0:
                income += value
            else:
                expense += -value
    else:
        return None

    return {
        "rows": len(rows),
        "total_income": round(income, 2),
        "total_expense": round(expense, 2),
        "balance": round(income - expense, 2),
    }


def index_user_csv(user_id: str, file_path: str, filename: str) -> int:
    """Embed a CSV into the user's store (replacing any earlier upload). Returns row count."""
    documents = CSVLoader(file_path=file_path, encoding="utf-8-sig").load()
    if not documents:
        return 0
    for doc in documents:
        doc.metadata["source"] = f"{filename}, row {doc.metadata.get('row', 0) + 1}"

    chunks = text_splitter.split_documents(documents)

    store = _open_store(user_id)
    store.delete_collection()
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=_collection_name(user_id),
        persist_directory=DATA_DIR,
    )

    try:
        stats = compute_csv_stats(file_path)
    except Exception:
        logger.exception("Could not compute CSV stats")
        stats = None
    path = _stats_path(user_id)
    if stats:
        path.write_text(json.dumps(stats))
    else:
        path.unlink(missing_ok=True)

    return len(documents)


# ─────────────────────────────────────
# QUESTION ANSWERING
# ─────────────────────────────────────

NO_DOCS = "No document uploaded yet. Upload a CSV statement first."


def query_documents(user_id: str, question: str) -> dict:
    """Retrieval-augmented answer with the rows it was based on."""
    store = get_user_store(user_id)
    if store is None:
        return {"answer": NO_DOCS, "sources": []}

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=store.as_retriever(search_type="similarity", search_kwargs={"k": 4}),
        return_source_documents=True,
    )
    result = qa_chain.invoke({"query": question})
    sources = list(dict.fromkeys(d.metadata.get("source", "Unknown") for d in result.get("source_documents", [])))
    return {"answer": result["result"], "sources": sources}


def hybrid_search(user_id: str, query: str, k: int = 3) -> List[str]:
    """Merge semantic matches with keyword matches, semantic first."""
    store = get_user_store(user_id)
    if store is None:
        return []

    combined: List[str] = []
    for doc in store.similarity_search(query, k=k * 2):
        if doc.page_content not in combined:
            combined.append(doc.page_content)

    keywords = query.lower().split()
    scored = []
    for content in store._collection.get()["documents"]:
        score = sum(1 for kw in keywords if kw in content.lower())
        if score:
            scored.append((score, content))
    for _, content in sorted(scored, key=lambda x: x[0], reverse=True)[:k]:
        if content not in combined:
            combined.append(content)

    return combined[:k]


# ─────────────────────────────────────
# REACT AGENT (tools bound to one user's store)
# ─────────────────────────────────────

REACT_TEMPLATE = """You are a helpful AI assistant for a personal finance app.

The user may have uploaded a CSV of their transactions. It is searchable through
your tools. If they ask about "the document", "my data" or "my file", use the tools.
Never invent numbers: totals come from the summary tool.

You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}"""


def create_agent(user_id: str) -> AgentExecutor:
    store = get_user_store(user_id)

    @tool
    def search_transactions(query: str) -> str:
        """Search the user's uploaded transactions for rows matching a query."""
        if store is None:
            return NO_DOCS
        return "\n".join(d.page_content for d in store.similarity_search(query, k=5))

    @tool
    def analyze_spending_patterns(category: str) -> str:
        """Find and total the user's spending related to one category, e.g. food or travel."""
        if store is None:
            return NO_DOCS
        rows = "\n".join(d.page_content for d in store.similarity_search(f"spending in {category}", k=15))
        prompt = (
            f"Records:\n{rows}\n\nTotal the amounts spent on '{category}' (include close synonyms). "
            f"Reply exactly: Found [count] transactions related to {category} totaling [amount]. "
            "If amounts cannot be determined, say so instead of guessing."
        )
        return llm.invoke(prompt).content

    @tool
    def get_summary_stats(query: str = "") -> str:
        """Get total income, total expenses and balance for the uploaded document."""
        path = _stats_path(user_id)
        if path.exists():
            s = json.loads(path.read_text())
            return (
                f"Rows: {s['rows']}\nTotal Income: {money(s['total_income'])}\n"
                f"Total Expenses: {money(s['total_expense'])}\nBalance: {money(s['balance'])}"
            )
        if store is None:
            return NO_DOCS
        return "Totals could not be calculated: the CSV's amount columns were not recognised."

    @tool
    def answer_general_question(question: str) -> str:
        """Answer a general personal-finance question that does not need the user's data."""
        return llm.invoke(question).content

    tools = [search_transactions, analyze_spending_patterns, get_summary_stats, answer_general_question]
    agent = create_react_agent(llm, tools, PromptTemplate.from_template(REACT_TEMPLATE))
    return AgentExecutor(agent=agent, tools=tools, handle_parsing_errors=True, max_iterations=6)


def query_with_agent(user_id: str, question: str) -> str:
    if get_user_store(user_id) is None:
        return NO_DOCS
    return create_agent(user_id).invoke({"input": question})["output"]
