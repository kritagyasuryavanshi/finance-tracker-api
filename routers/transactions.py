from fastapi import APIRouter, HTTPException,Query
from typing import List,Optional
import database
from models.transaction import (
    Transaction,
    TransactionCreate,
    TransactionSummary,
    DeleteResponse
)



router = APIRouter(
    prefix = "/transactions",
    tags = ["Transactions"]
)

@router.get("/",response_model=List[Transaction])
async def get_all_transactions(
    transaction_type: Optional[str] = Query(
        default=None,
        description="Filter by 'income' or 'expense'"
    )
):
    
    transactions = database.get_all_transactions()

    if transaction_type:
        if transaction_type not in ["income","expense"]:
            raise HTTPException(status_code=400, detail="transaction_type must be 'income' or 'expense'")
        
        transactions = [
            t for t in transactions
            if t["type"] == transaction_type
        ]

        
    return transactions



@router.get("/summary", response_model=TransactionSummary)
async def get_summary():
    """Get financial summary with totals and balance"""
    return database.get_summary()



@router.get("/{transaction_id}",response_model=Transaction)
async def get_transaction_by_id(transaction_id:str):
    transaction = database.get_transatin_by_id(transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction



@router.post("/",response_model=Transaction,status_code=201)
async def create_transaction(transaction:TransactionCreate):
    data = {
        "type": transaction.type.value,
        "category": transaction.category,
        "amount": transaction.amount,
        "description": transaction.description or ""
    }

    created = database.create_transaction(data)
    return created        


@router.delete("/{transaction_id}",response_model=DeleteResponse)
async def delete_transaction(transaction_id:str):

    deleted = database.delete_transaction(transaction_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found")
    return {
        "success": True,
        "message": f"Transaction '{transaction_id}' deleted successfully"
    }

