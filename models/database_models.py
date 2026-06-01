from sqlalchemy import  Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

base = declarative_base()

class TransactionType(str,enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"

class Transaction(base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True)
    date = Column(String, nullable=False)
    type = Column(String, nullable=False)
    category = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(String)

    class Config:
        from_attributes = True