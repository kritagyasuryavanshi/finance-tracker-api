# routers/transactions.py
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from db import get_db
import database
from models.transaction import (
    Transaction,
    TransactionCreate,
    TransactionSummary,
    DeleteResponse
)

router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"]
)


@router.get("/", response_model=List[Transaction])
async def get_all_transactions(
    transaction_type: Optional[str] = Query(default=None),
    db: Session = Depends(get_db)
):
    """Get all transactions"""
    if transaction_type and transaction_type not in ["income", "expense"]:
        raise HTTPException(
            status_code=400,
            detail="transaction_type must be 'income' or 'expense'"
        )
    
    transactions = database.get_all_transactions(db, transaction_type)
    return transactions


@router.get("/summary", response_model=TransactionSummary)
async def get_summary(db: Session = Depends(get_db)):
    """Get financial summary"""
    return database.get_summary(db)


@router.get("/{transaction_id}", response_model=Transaction)
async def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """Get single transaction"""
    transaction = database.get_transaction_by_id(db, transaction_id)
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Not found")
    
    return transaction


@router.post("/", response_model=Transaction, status_code=201)
async def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db)
):
    """Create new transaction"""
    data = {
        "type": transaction.type.value,
        "category": transaction.category,
        "amount": transaction.amount,
        "description": transaction.description or ""
    }
    
    return database.create_transaction(db, data)


@router.delete("/{transaction_id}", response_model=DeleteResponse)
async def delete_transaction(
    transaction_id: str,
    db: Session = Depends(get_db)
):
    """Delete transaction"""
    deleted = database.delete_transaction(db, transaction_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
    
    return {
        "success": True,
        "message": "Transaction deleted successfully"
    }