# models/database_models.py
"""
SQLAlchemy models for database
Defines the database schema
"""

from sqlalchemy import Column, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum


# ─────────────────────────────────────
# CREATE BASE
# This is what gets imported in db.py
# ─────────────────────────────────────
Base = declarative_base()


# ─────────────────────────────────────
# TRANSACTION MODEL
# Maps to PostgreSQL table
# ─────────────────────────────────────
class TransactionModel(Base):
    """Database model for transactions"""
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.utcnow)
    type = Column(String, index=True)
    category = Column(String)
    amount = Column(Float)
    description = Column(String, default="")

    class Config:
        from_attributes = True