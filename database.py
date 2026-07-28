# database.py
"""
Database operations using SQLAlchemy + PostgreSQL
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from models.database_models import TransactionModel
from models.user import UserModel
from db import SessionLocal


def get_db() -> Session:
    """Get database session"""
    return SessionLocal()


# ─────────────────────────────────────
# TRANSACTION OPERATIONS
# ─────────────────────────────────────

def get_all_transactions(
    db: Session,
    transaction_type: Optional[str] = None,
    user_id: Optional[str] = None
) -> List[dict]:
    """Get all transactions"""
    query = db.query(TransactionModel)
    
    if user_id:
        query = query.filter(TransactionModel.user_id == user_id)
    
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


def get_transaction_by_id(
    db: Session,
    transaction_id: str,
    user_id: Optional[str] = None  # ← Optional now
) -> Optional[dict]:
    """Get single transaction by ID"""
    query = db.query(TransactionModel).filter(
        TransactionModel.id == transaction_id
    )
    
    if user_id:
        query = query.filter(TransactionModel.user_id == user_id)
    
    transaction = query.first()
    
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
        user_id=data.get("user_id")  # ← .get() so it's optional
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


def delete_transaction(
    db: Session,
    transaction_id: str,
    user_id: Optional[str] = None
) -> bool:
    """Delete transaction"""
    # Build query first, filter after
    query = db.query(TransactionModel).filter(
        TransactionModel.id == transaction_id
    )
    
    if user_id:
        query = query.filter(TransactionModel.user_id == user_id)
    
    transaction = query.first()
    
    if not transaction:
        return False
    
    db.delete(transaction)
    db.commit()
    return True


def get_summary(
    db: Session,
    user_id: Optional[str] = None
) -> dict:
    """Get financial summary"""
    query = db.query(TransactionModel)
    
    if user_id:
        query = query.filter(TransactionModel.user_id == user_id)
    
    transactions = query.all()
    
    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expense = sum(t.amount for t in transactions if t.type == "expense")
    
    return {
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "balance": round(total_income - total_expense, 2),
        "transaction_count": len(transactions),
    }


# ─────────────────────────────────────
# USER OPERATIONS
# ─────────────────────────────────────

def get_user_by_email(db: Session, email: str) -> Optional[Dict]:
    """Find user by email"""
    user = db.query(UserModel).filter(
        UserModel.email == email
    ).first()
    
    if not user:
        return None
    
    return {
        "id": user.id,
        "email": user.email,
        "password_hash": user.password_hash,
        "created_at": str(user.created_at)
    }


def get_user_by_id(db: Session, user_id: str) -> Optional[Dict]:
    """Find user by ID"""
    user = db.query(UserModel).filter(
        UserModel.id == user_id
    ).first()
    
    if not user:
        return None
    
    return {
        "id": user.id,
        "email": user.email,
        "created_at": str(user.created_at)
        # ↑ NO password_hash! Never expose it!
    }


def create_user(db: Session, email: str, password_hash: str) -> Dict:
    """Create new user"""
    existing = get_user_by_email(db, email)
    if existing:
        raise ValueError("Email already registered")
    
    user = UserModel(
        id=str(uuid.uuid4()),
        email=email,
        password_hash=password_hash
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return {
        "id": user.id,
        "email": user.email,
        "created_at": str(user.created_at)
    }