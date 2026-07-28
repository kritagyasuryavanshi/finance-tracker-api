# models/user.py
from sqlalchemy import Column, String, DateTime
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional
from models.database_models import Base


# ─────────────────────────────────────
# DATABASE MODEL (SQLAlchemy)
# Creates "users" table in PostgreSQL
# ─────────────────────────────────────
class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────
# PYDANTIC MODELS (API Schemas)
# ─────────────────────────────────────

class UserSignup(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


class UserResponse(BaseModel):
    id: str
    email: str
    created_at: str