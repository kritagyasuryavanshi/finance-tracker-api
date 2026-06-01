from pydantic import BaseModel,Field
from typing import Optional
from enum import Enum

class TransactionType(str,Enum):
    INCOME = "income"
    EXPENSE = "expense"


class TransactionCreate(BaseModel):
    type: TransactionType
    category: str = Field(...,min_length=1,max_length=50)
    amount:float = Field(...,gt=0)
    description: Optional[str] = Field(default="", max_length=200)

    model_config = {
        "json_schema_extra":{
            "example": {
                "type": "income",
                "category": "Salary",
                "amount": 5000.00,
                "description": "Monthly salary for June"
            }
        }
    }


class Transaction(BaseModel):
        id:str
        date:str
        type:str
        category:str
        amount:float
        description: Optional[str] = None

class TransactionSummary(BaseModel):
    """
    Financial summary response
    """
    total_income: float
    total_expense: float
    balance: float
    transaction_count: int

class DeleteResponse(BaseModel):
    message:str
    success:bool