"""
One-click demo accounts.

Each "Try the demo" click gets its own throwaway user pre-filled with two months
of realistic transactions, so visitors never see each other's data. Demo users
older than DEMO_TTL_HOURS are deleted whenever a new one is created.
"""

import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models.database_models import TransactionModel
from models.user import UserModel
from services.auth_service import hash_password

DEMO_DOMAIN = "demo.local"
DEMO_TTL_HOURS = 24

# (days ago, type, category, amount in INR, description)
DEMO_TRANSACTIONS = [
    (58, "income", "Salary", 85000, "September salary"),
    (57, "expense", "Rent", 22000, "Monthly rent"),
    (55, "expense", "Investments", 10000, "Index fund SIP"),
    (52, "expense", "Groceries", 3200, "Weekly groceries"),
    (49, "expense", "Dining", 1450, "Dinner with friends"),
    (46, "expense", "Utilities", 2400, "Electricity + internet"),
    (44, "income", "Freelance", 15000, "API integration project"),
    (41, "expense", "Transport", 1800, "Metro card + cabs"),
    (38, "expense", "Groceries", 2900, "Weekly groceries"),
    (35, "expense", "Shopping", 4600, "Running shoes"),
    (33, "expense", "Subscriptions", 799, "Streaming"),
    (28, "income", "Salary", 85000, "October salary"),
    (27, "expense", "Rent", 22000, "Monthly rent"),
    (25, "expense", "Investments", 10000, "Index fund SIP"),
    (22, "expense", "Groceries", 3400, "Weekly groceries"),
    (19, "expense", "Dining", 2650, "Weekend food delivery"),
    (16, "expense", "Utilities", 2550, "Electricity + internet"),
    (14, "expense", "Health", 1200, "Pharmacy"),
    (11, "expense", "Transport", 2100, "Metro card + cabs"),
    (8, "expense", "Groceries", 3100, "Weekly groceries"),
    (5, "expense", "Travel", 6800, "Train tickets for Diwali"),
    (3, "expense", "Subscriptions", 799, "Streaming"),
    (1, "expense", "Dining", 980, "Lunch meetings"),
]


def _delete_expired_demo_users(db: Session) -> None:
    cutoff = datetime.utcnow() - timedelta(hours=DEMO_TTL_HOURS)
    expired = (
        db.query(UserModel)
        .filter(UserModel.email.like(f"%@{DEMO_DOMAIN}"), UserModel.created_at < cutoff)
        .all()
    )
    for user in expired:
        db.query(TransactionModel).filter(TransactionModel.user_id == user.id).delete()
        db.delete(user)
    if expired:
        db.commit()


def create_demo_user(db: Session) -> dict:
    """Create a fresh demo user with seeded transactions and return it."""
    _delete_expired_demo_users(db)

    now = datetime.utcnow()
    user = UserModel(
        id=str(uuid.uuid4()),
        email=f"demo-{secrets.token_hex(4)}@{DEMO_DOMAIN}",
        # Random password nobody knows: demo users can only enter through /auth/demo
        password_hash=hash_password(secrets.token_urlsafe(16)),
        created_at=now,
    )
    db.add(user)

    for days_ago, tx_type, category, amount, description in DEMO_TRANSACTIONS:
        db.add(
            TransactionModel(
                id=str(uuid.uuid4()),
                date=now - timedelta(days=days_ago, hours=secrets.randbelow(10)),
                type=tx_type,
                category=category,
                amount=float(amount),
                description=description,
                user_id=user.id,
            )
        )

    db.commit()
    return {"id": user.id, "email": user.email}
