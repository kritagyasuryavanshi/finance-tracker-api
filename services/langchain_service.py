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
from langchain_classic.chains import RetrievalQA
from langchain_classic.agents import create_react_agent, AgentExecutor
from langchain_classic import hub
from langchain_core.tools import Tool, tool
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────────────

# Initialize Gemini
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    # ↑ Fast and cost-effective
    
    temperature=0.7,
    # ↑ Balance between consistency (0) and creativity (1)
)

# Initialize embeddings (for vector DB)
embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001"
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
def answer_general_question(question: str) -> str:
    """
    Answer any general question NOT related to the user's
    financial transactions or data — general knowledge,
    explanations, casual conversation, anything else.
    
    Use this when the question is NOT about searching
    transactions, analyzing spending, or financial summaries.
    """
    
    response = llm.invoke(question)
    # ↑ Direct call to Gemini, no tool/retrieval needed
    #   Just answer like a normal chatbot would
    
    return response.content

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
    results = vectorstore.similarity_search(query, k=15)
    
    if not results:
        return f"No transactions found related to {category}"
    
    # Let the AI read the raw documents and calculate
    # instead of brittle string-splitting on exact column names
    raw_data = "\n".join([doc.page_content for doc in results])
    
    prompt = f"""Below are financial transaction records in raw text form.
The column names and format may vary (e.g. "Amount" or "amount" or "value",
"Category" or "type" or "tag", etc). Read them carefully regardless of
exact column naming.

RECORDS:
{raw_data}

Calculate the total amount spent specifically related to "{category}"
(include similar/related terms, e.g. "food" should include "groceries",
"restaurant", "dining" etc if present).

Respond in this exact format:
Found [count] transactions related to {category} totaling $[total]

If you cannot determine amounts from the data, say so clearly instead of guessing.
"""
    
    response = llm.invoke(prompt)
    return response.content

@tool
def get_summary_stats() -> str:
    """
    Get overall financial summary
    
    Use when user asks about total spending, balance, etc.
    """
    
    if vectorstore is None:
        return "No data loaded"
    
    results = vectorstore.similarity_search("transactions", k=100)
    
    if not results:
        return "No transaction data found"
    
    raw_data = "\n".join([doc.page_content for doc in results])
    
    prompt = f"""Below are financial transaction records in raw text form.
The column names and format may vary across rows or files. Read them
carefully regardless of exact column naming (e.g. "Amount" vs "amount"
vs "value", "Type" vs "category" indicating income/expense, etc).

RECORDS:
{raw_data}

Calculate and respond in this exact format:
Total Income: $[amount]
Total Expenses: $[amount]
Balance: $[amount]

If the data doesn't clearly indicate income vs expense, make a reasonable
judgment (e.g. salary/refund/deposit = income, purchases/bills = expense)
and note your assumption briefly.
"""
    
    response = llm.invoke(prompt)
    return response.content

def create_agent():
    """
    Create multi-agent system
    
    Agent can use multiple tools to solve complex questions
    """
    
    # Define tools
    tools = [
        search_transactions,
        analyze_spending_patterns,
        get_summary_stats,
        answer_general_question
    ]
    
    # Write our own ReAct prompt (no external download needed)
    # ReAct = the agent THINKS, then ACTS, then OBSERVES, repeat
    from langchain_core.prompts import PromptTemplate
    
    react_template = """You are a helpful AI assistant for a personal finance app.

IMPORTANT CONTEXT: The user may have already uploaded a CSV document
containing their financial transactions. This data is NOT a separate
"document" you read directly — instead, it has been processed and is
searchable through your tools (search_transactions, analyze_spending_patterns,
get_summary_stats). If the user asks about "the document", "my data",
"my file", or "what I uploaded", treat this as a request to search or
summarize their transaction data using your tools.

Answer the following question as best you can. You have access to the following tools:

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

    prompt = PromptTemplate.from_template(react_template)
    
    # Create agent
    agent = create_react_agent(llm, tools, prompt)
    # Create executor
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
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