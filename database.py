# import csv
# import os
# import uuid
# from datetime import datetime
# from typing import List, Dict,Optional



# TRANSACTON_FILE = "data/transactions.csv"
# FIELDNAMES = ["id","date","type","category","amount","description"]


# def _ensure_data_dir():
#     os.makedirs("data",exist_ok=True)

# def get_all_transactions() ->List[Dict]:
#     _ensure_data_dir()
    
#     if not os.path.isfile(TRANSACTON_FILE):
#         return []
#     transactions = []
#     with open(TRANSACTON_FILE,mode="r") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             row['amount'] = float(row["amount"])
#             transactions.append(row)
#     return transactions

# def get_transatin_by_id(transaction_id:str) -> Optional[Dict]:
#     transactions = get_all_transactions()
#     for t in transactions:
#         if t["id"]==transaction_id:
#             return t
#     return None

# def create_transaction(data:Dict)->Dict:
#     _ensure_data_dir()

#     transaction ={
#         "id": str(uuid.uuid4()),
#         "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#         "type": data["type"],
#         "category": data["category"],
#         "amount": data["amount"],
#         "description": data.get("description","")
#     }


#     file_exists = os.path.isfile(TRANSACTON_FILE)
#     with open(TRANSACTON_FILE,mode="a",newline="") as file:
#         writer = csv.DictWriter(file,fieldnames=FIELDNAMES)
#         if not file_exists:
#             writer.writeheader()
#         writer.writerow(transaction)

#     return transaction


# def delete_transaction(transaction_id:str)->bool:
#     transactions = get_all_transactions()
#     original_count = len(transactions)

#     updated_transactions = [t for t in transactions if  t["id"]!=transaction_id]
    
#     if len(updated_transactions) == original_count:
#         return False
    
#     with open(TRANSACTON_FILE,mode="w",newline="") as file:
#         writer = csv.DictWriter(file,fieldnames=FIELDNAMES)
#         writer.writeheader()
#         writer.writerows(updated_transactions)
#     return True

# def get_summary() -> Dict:
#     """Calculate total income, expenses and balance"""
#     transactions = get_all_transactions()

#     total_income = sum(
#         t['amount'] for t in transactions
#         if t['type'] == 'income'
#     )
#     total_expense = sum(
#         t['amount'] for t in transactions
#         if t['type'] == 'expense'
#     )

#     return {
#         "total_income": round(total_income, 2),
#         "total_expense": round(total_expense, 2),
#         "balance": round(total_income - total_expense, 2),
#         "transaction_count": len(transactions)
#     }

# database.py
"""
Database operations using SQLAlchemy + PostgreSQL
"""

import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from models.database_models import TransactionModel
from db import SessionLocal


def get_db() -> Session:
    """Get database session"""
    return SessionLocal()


def get_all_transactions(db: Session, transaction_type: Optional[str] = None) -> List[dict]:
    """Get all transactions"""
    query = db.query(TransactionModel)
    
    if transaction_type:
        query = query.filter(TransactionModel.type == transaction_type)
    
    transactions = query.all()
    
    return [
        {
            "id": t.id,
            "date": t.date.strftime("%Y-%m-%d %H:%M:%S"),
            "type": t.type,
            "category": t.category,
            "amount": t.amount,
            "description": t.description,
        }
        for t in transactions
    ]


def get_transaction_by_id(db: Session, transaction_id: str) -> Optional[dict]:
    """Get single transaction by ID"""
    transaction = db.query(TransactionModel).filter(
        TransactionModel.id == transaction_id
    ).first()
    
    if not transaction:
        return None
    
    return {
        "id": transaction.id,
        "date": transaction.date.strftime("%Y-%m-%d %H:%M:%S"),
        "type": transaction.type,
        "category": transaction.category,
        "amount": transaction.amount,
        "description": transaction.description,
    }


def create_transaction(db: Session, data: dict) -> dict:
    """Create new transaction"""
    transaction = TransactionModel(
        id=str(uuid.uuid4()),
        date=datetime.utcnow(),
        type=data["type"],
        category=data["category"],
        amount=data["amount"],
        description=data.get("description", ""),
    )
    
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    return {
        "id": transaction.id,
        "date": transaction.date.strftime("%Y-%m-%d %H:%M:%S"),
        "type": transaction.type,
        "category": transaction.category,
        "amount": transaction.amount,
        "description": transaction.description,
    }


def delete_transaction(db: Session, transaction_id: str) -> bool:
    """Delete transaction"""
    transaction = db.query(TransactionModel).filter(
        TransactionModel.id == transaction_id
    ).first()
    
    if not transaction:
        return False
    
    db.delete(transaction)
    db.commit()
    
    return True


def get_summary(db: Session) -> dict:
    """Get financial summary"""
    transactions = db.query(TransactionModel).all()
    
    total_income = sum(
        t.amount for t in transactions if t.type == "income"
    )
    total_expense = sum(
        t.amount for t in transactions if t.type == "expense"
    )
    
    return {
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "balance": round(total_income - total_expense, 2),
        "transaction_count": len(transactions),
    }