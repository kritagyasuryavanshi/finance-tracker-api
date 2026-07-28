import os
import uuid
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
# ↑ python-jose library
#   jwt.encode() = create token
#   jwt.decode() = verify + read token
#   JWTError = raised when token is invalid

from passlib.context import CryptContext
# ↑ passlib's password hashing context
#   Handles bcrypt for us

from dotenv import load_dotenv
from pygments import token


load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-this-in-production")
# ↑ Used to SIGN JWT tokens
#   Anyone with this key can create valid tokens
#   MUST be secret! Store in .env only
#   Default is for development only

ALGORITHM = "HS256"
# ↑ Hashing algorithm for JWT
#   HS256 = HMAC with SHA-256
#   Industry standard, fast and secure

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
# ↑ Token expires after 24 hours
#   = 1440 minutes
#   After this, user must log in again


# ─────────────────────────────────────
# PASSWORD HASHING
# ─────────────────────────────────────

pwd_context = CryptContext(
    schemes=["bcrypt"],
    # ↑ Use bcrypt algorithm
    #   Automatically salts the hash
    #   (salt = random data added before hashing
    #    prevents rainbow table attacks)
    
    deprecated="auto"
    # ↑ Auto-handle deprecated schemes
)

def hash_password(password: str) -> str:
    """
    Convert plain password to bcrypt hash
    
    EXAMPLE:
    hash_password("secret123")
    → "$2b$12$KIXxPfn8d...8aB3xY9w"
    
    This hash is what we store in database
    NEVER store the original "secret123"!
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Check if plain password matches stored hash
    
    EXAMPLE:
    verify_password("secret123", "$2b$12$KIXxPfn8d...8aB3xY9w")
    → True (matches!)
    
    verify_password("wrongpass", "$2b$12$KIXxPfn8d...8aB3xY9w")
    → False (doesn't match)
    
    HOW IT WORKS:
    bcrypt re-hashes the plain password with same salt
    Compares result with stored hash
    No need to "decrypt" - just re-hash and compare!
    """
    return pwd_context.verify(plain_password, hashed_password)


# ─────────────────────────────────────
# JWT TOKEN OPERATIONS
# ─────────────────────────────────────

def create_access_token(user_id: str, email: str) -> str:
    """
    Create a signed JWT token for a user
    
    WHAT GOES INSIDE THE TOKEN:
    {
        "sub": "abc-123",        # Subject (user ID)
        "email": "user@email.com",
        "exp": 1735689600        # Expiry timestamp
    }
    
    This gets SIGNED with SECRET_KEY
    Result: "eyJhbGc...xyz789"
    """
    
    # Set expiry time
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # ↑ Current time + 24 hours
    
    # Build token payload
    payload = {
        "sub": user_id,
        # ↑ "sub" = subject (who this token is for)
        #   Standard JWT claim name
        
        "email": email,
        # ↑ Email for convenience
        #   Frontend can read this without another API call
        
        "exp": expire,
        # ↑ Expiry time
        #   python-jose auto-checks this on decode!
    }
    
    # Create and sign the token
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    # ↑ jwt.encode() does 3 things:
    #   1. Encodes payload as base64
    #   2. Signs with SECRET_KEY
    #   3. Returns: "eyJhbGc...xyz789"
    
    return token

def verify_token(token: str) -> Optional[dict]:
    """
    Verify a JWT token and return its payload
    
    RETURNS:
    If valid: {"sub": "abc-123", "email": "user@email.com"}
    If invalid/expired: None
    
    CHECKS:
    ✅ Was this signed with our SECRET_KEY?
    ✅ Has it expired?
    ✅ Is it properly formatted?
    """
    
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
            # ↑ Must match algorithm used to create token
        )
        # ↑ If ANY check fails, raises JWTError
        #   If expired, raises ExpiredSignatureError
        #   (which is a subclass of JWTError)
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        # ↑ Token must have a user_id
        #   Malformed token? Return None
        
        return payload
        # ↑ Return full payload
        #   Caller can extract user_id, email, etc.
    
    except JWTError:
        # ↑ Catches ALL JWT errors:
        #   - Invalid signature (token was tampered with)
        #   - Token expired
        #   - Malformed token
        return None
        # ↑ Any error = invalid token = return None