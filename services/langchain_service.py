# services/langchain_service.py
"""
LangChain RAG System

Handles:
- Document loading
- Vector embeddings
- Retrieval
- AI chains
- Multi-agent systems
"""

import os
from typing import List, Optional
import tempfile
from pathlib import Path

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import CSVLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub
from langchain.tools import Tool, tool

from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────────────

# Initialize Gemini
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    # ↑ Fast and cost-effective
    
    temperature=0.7,
    # ↑ Balance between consistency (0) and creativity (1)
)

# Initialize embeddings (for vector DB)
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/embedding-001"
    # ↑ Converts text to vectors
)

# Text splitter (chunks large documents)
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    # ↑ Each chunk ~1000 characters
    #   Not too small (loses context)
    #   Not too big (loses specificity)
    
    chunk_overlap=200,
    # ↑ Overlap between chunks
    #   Prevents losing info at boundaries
)

# Global vector store
vectorstore = None
# ↑ Loaded after user uploads file


# ─────────────────────────────────────────────────────
# PART 1: DOCUMENT LOADING & PROCESSING
# ─────────────────────────────────────────────────────

def load_and_process_csv(file_path: str) -> List:
    """
    Load CSV file and process into documents
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        List of processed documents
    """
    
    # Step 1: Load CSV
    loader = CSVLoader(
        file_path=file_path,
        source_column="Date"
        # ↑ Use Date column as source identifier
    )
    
    documents = loader.load()
    # ↑ Each row becomes a document
    
    # Step 2: Split into chunks
    # (for very large CSVs)
    chunks = text_splitter.split_documents(documents)
    
    return chunks


def create_vector_store(documents: List):
    """
    Create vector database from documents
    
    Args:
        documents: List of documents to embed
    """
    
    global vectorstore
    
    # Create Chroma vector store
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory="./chroma_db"
        # ↑ Save locally so we don't re-embed
    )
    # ↑ Each document is converted to embedding
    #   Stored in Chroma DB
    #   Ready for searches


# ─────────────────────────────────────────────────────
# PART 2: SIMPLE RAG CHAINS
# ─────────────────────────────────────────────────────

def create_qa_chain():
    """
    Create RetrievalQA chain
    
    This is the simplest RAG approach
    User asks question → Retrieve docs → Answer
    """
    
    if vectorstore is None:
        return None
    
    # Create retriever from vectorstore
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        # ↑ Find docs similar to question
        
        search_kwargs={"k": 3}
        # ↑ Return top 3 most similar docs
    )
    
    # Create QA chain
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        # ↑ "stuff" = stuff all docs into prompt
        #   (vs. map_reduce for very large docs)
        
        retriever=retriever,
        return_source_documents=True
        # ↑ Return which docs were used
    )
    
    return qa_chain


def query_documents(question: str) -> dict:
    """
    Ask a question about uploaded documents
    
    Args:
        question: User's question
        
    Returns:
        {"answer": "...", "sources": [...]}
    """
    
    qa_chain = create_qa_chain()
    
    if qa_chain is None:
        return {
            "answer": "No documents loaded. Upload a CSV first!",
            "sources": []
        }
    
    try:
        result = qa_chain.invoke({"query": question})
        
        return {
            "answer": result["result"],
            "sources": [
                doc.metadata.get("source", "Unknown")
                for doc in result.get("source_documents", [])
            ]
        }
    
    except Exception as e:
        return {
            "answer": f"Error: {str(e)}",
            "sources": []
        }


# ─────────────────────────────────────────────────────
# PART 3: MULTI-AGENT SYSTEM
# ─────────────────────────────────────────────────────

@tool
def search_transactions(query: str) -> str:
    """
    Search transactions by description
    
    Use when user asks about specific transactions
    """
    
    if vectorstore is None:
        return "No data loaded"
    
    results = vectorstore.similarity_search(query, k=5)
    
    # Format results
    formatted = "\n".join([doc.page_content for doc in results])
    return formatted


@tool
def analyze_spending_patterns(category: str) -> str:
    """
    Analyze spending in a specific category
    
    Use when user asks about category trends
    """
    
    if vectorstore is None:
        return "No data loaded"
    
    query = f"spending in {category}"
    results = vectorstore.similarity_search(query, k=10)
    
    # Calculate total from results
    total = 0
    count = 0
    
    for doc in results:
        # Extract amount from document
        # (this is simplified - real version would parse better)
        content = doc.page_content
        if "Amount:" in content:
            try:
                amount = float(content.split("Amount:")[-1].split(",")[0].strip())
                total += amount
                count += 1
            except:
                pass
    
    return f"Found {count} transactions in {category} totaling ${total:.2f}"


@tool
def get_summary_stats() -> str:
    """
    Get overall financial summary
    
    Use when user asks about total spending, balance, etc.
    """
    
    if vectorstore is None:
        return "No data loaded"
    
    # Retrieve all documents
    results = vectorstore.similarity_search("transactions", k=100)
    
    total_income = 0
    total_expense = 0
    
    for doc in results:
        content = doc.page_content.lower()
        
        # Look for income/expense markers
        if "income" in content:
            try:
                amount = float(content.split("amount:")[-1].split(",")[0].strip())
                total_income += amount
            except:
                pass
        elif "expense" in content:
            try:
                amount = float(content.split("amount:")[-1].split(",")[0].strip())
                total_expense += amount
            except:
                pass
    
    balance = total_income - total_expense
    
    return f"""
    Financial Summary:
    - Total Income: ${total_income:.2f}
    - Total Expenses: ${total_expense:.2f}
    - Balance: ${balance:.2f}
    """


def create_agent():
    """
    Create multi-agent system
    
    Agent can use multiple tools to solve complex questions
    """
    
    # Define tools
    tools = [
        search_transactions,
        analyze_spending_patterns,
        get_summary_stats
    ]
    
    # Use ReAct prompt (Reasoning + Acting)
    prompt = hub.pull("hwchase17/react")
    
    # Create agent
    agent = create_react_agent(llm, tools, prompt)
    
    # Create executor
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        # ↑ Show agent's thinking process
    )
    
    return executor


def query_with_agent(question: str) -> str:
    """
    Ask complex questions using multi-agent system
    
    Agent can:
    - Search transactions
    - Analyze patterns
    - Get summaries
    - Combine information
    
    Args:
        question: User's question
        
    Returns:
        Comprehensive answer
    """
    
    try:
        executor = create_agent()
        result = executor.invoke({"input": question})
        return result["output"]
    
    except Exception as e:
        return f"Error: {str(e)}"


# ─────────────────────────────────────────────────────
# PART 4: ADVANCED RAG - HYBRID SEARCH
# ─────────────────────────────────────────────────────

def hybrid_search(query: str, k: int = 3) -> List:
    """
    Hybrid search combining multiple strategies
    
    1. Semantic search (similar meaning)
    2. Keyword search (exact matches)
    3. Re-ranking (best results first)
    """
    
    if vectorstore is None:
        return []
    
    # Semantic search
    semantic_results = vectorstore.similarity_search(query, k=k*2)
    
    # Keyword search (simple implementation)
    keywords = query.lower().split()
    keyword_results = []
    
    all_docs = vectorstore._collection.get()
    for doc_id, doc_content in zip(all_docs["ids"], all_docs["documents"]):
        score = sum(1 for kw in keywords if kw in doc_content.lower())
        if score > 0:
            keyword_results.append((doc_content, score))
    
    # Sort by keyword score
    keyword_results.sort(key=lambda x: x[1], reverse=True)
    
    # Combine and deduplicate
    combined = []
    seen = set()
    
    for doc in semantic_results:
        if doc.page_content not in seen:
            combined.append(doc)
            seen.add(doc.page_content)
    
    for content, score in keyword_results[:k]:
        if content not in seen:
            combined.append(content)
            seen.add(content)
    
    return combined[:k]