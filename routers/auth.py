"""
Authentication endpoints

POST /auth/signup  - Create new account
POST /auth/login   - Login with email/password
GET  /auth/me      - Get current user info (protected)
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# ↑ HTTPBearer = reads "Authorization: Bearer TOKEN" header
#   HTTPAuthorizationCredentials = the parsed credentials

from sqlalchemy.orm import Session

import database
from db import get_db
from models.user import UserSignup, UserLogin, TokenResponse, UserResponse
from services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    verify_token
)


router = APIRouter(
    prefix="/auth",
    tags=["🔐 Authentication"]
)

# Security scheme for reading Bearer token from headers
security = HTTPBearer()
# ↑ FastAPI will automatically read:
#   Authorization: Bearer eyJhbGc...xyz789
#   And pass it to functions that use security


# ─────────────────────────────────────
# DEPENDENCY: Get Current User
# Used by ALL protected routes
# ─────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> dict:
    """
    Dependency that extracts and validates current user from JWT token
    
    HOW IT'S USED:
    @router.get("/protected-route")
    async def protected(user = Depends(get_current_user)):
        # user = {"id": "abc-123", "email": "..."}
        # If token invalid → automatically returns 401!
    
    WHAT IT DOES:
    1. Reads Bearer token from Authorization header
    2. Verifies token signature and expiry
    3. Extracts user_id from token
    4. Fetches user from database
    5. Returns user dict
    6. If ANY step fails → raises 401 Unauthorized
    """
    token = credentials.credentials

    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token") 
    
    user_id = payload.get("sub")
    user = database.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")   
    return user

# ─────────────────────────────────────
# POST /auth/signup
# Create new account
# ─────────────────────────────────────

@router.post("/signup", response_model=TokenResponse)
async def signup(
    user_data: UserSignup,
    db: Session = Depends(get_db)
):
    """
    Create new user account
    
    FRONTEND SENDS:
    POST /auth/signup
    {
        "email": "kritagya@email.com",
        "password": "secret123"
    }
    
    RETURNS:
    {
        "access_token": "eyJhbGc...",
        "token_type": "bearer",
        "user_id": "abc-123",
        "email": "kritagya@email.com"
    }
    """
    
    try:
        # Step 1: Hash the password
        password_hash = hash_password(user_data.password)
        # ↑ "secret123" → "$2b$12$KIXxPfn8d...8aB3xY9w"
        
        # Step 2: Create user in database
        user = database.create_user(
            db=db,
            email=user_data.email,
            password_hash=password_hash
        )
        # ↑ Raises ValueError if email already exists
        
        # Step 3: Create JWT token
        token = create_access_token(
            user_id=user["id"],
            email=user["email"]
        )
        
        # Step 4: Return token to frontend
        return TokenResponse(
            access_token=token,
            user_id=user["id"],
            email=user["email"]
        )
    
    except ValueError as e:
        # Email already exists
        raise HTTPException(
            status_code=400,
            detail=str(e)
            # "Email already registered"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Signup failed: {str(e)}"
        )

# ─────────────────────────────────────
# POST /auth/login
# Login with email/password
# ─

@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Login with existing account
    
    FRONTEND SENDS:
    POST /auth/login
    {
        "email": "kritagya@email.com",
        "password": "secret123"
    }
    
    RETURNS:
    {
        "access_token": "eyJhbGc...",
        "token_type": "bearer",
        "user_id": "abc-123",
        "email": "kritagya@email.com"
    }
    
    ERRORS:
    400 → "Invalid email or password"
    """
    
    # Step 1: Find user by email
    user = database.get_user_by_email(db, user_data.email)
    
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid email or password"
        )
    # ↑ IMPORTANT: Don't say "email not found"
    #   That tells attackers which emails exist!
    #   Always say "Invalid email OR password"
    
    # Step 2: Verify password
    password_valid = verify_password(
        user_data.password,
        user["password_hash"]
    )
    
    if not password_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid email or password"
        )
    # ↑ Same message as above - don't leak info
    
    # Step 3: Create JWT token
    token = create_access_token(
        user_id=user["id"],
        email=user["email"]
    )
    
    # Step 4: Return token
    return TokenResponse(
        access_token=token,
        user_id=user["id"],
        email=user["email"]
    )

# ─────────────────────────────────────
# GET /auth/me
# Get current logged-in user info
# ─────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: dict = Depends(get_current_user)
    # ↑ Depends(get_current_user) automatically:
    #   1. Reads token from header
    #   2. Verifies it
    #   3. Returns user dict
    #   4. If invalid → 401 (never reaches this function)
):
    """
    Get current user's info
    
    REQUIRES: Valid JWT token in Authorization header
    
    RETURNS:
    {
        "id": "abc-123",
        "email": "kritagya@email.com",
        "created_at": "2024-01-01 10:00:00"
    }
    """
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        created_at=current_user["created_at"]
    )