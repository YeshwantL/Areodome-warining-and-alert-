from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import os
import schemas, database, models

# Load env vars (or use defaults for dev)
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkeychangeinproduction")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

from cryptography.fernet import Fernet
import base64

# Derive a 32-byte key from SECRET_KEY for Fernet (Must be url-safe base64-encoded 32-byte key)
# For simplicity in this non-prod env, we pad/truncate standard key or generate one.
# Let's just generate a deterministic key based on SECRET_KEY so it persists across restarts if SECRET_KEY is constant.
def get_fernet():
    key = SECRET_KEY.encode()[:32].ljust(32, b'0')
    return Fernet(base64.urlsafe_b64encode(key))

def encrypt_password(password: str) -> str:
    f = get_fernet()
    return f.encrypt(password.encode()).decode()

def decrypt_password(encrypted_password: str) -> str:
    f = get_fernet()
    return f.decrypt(encrypted_password.encode()).decode()

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        sid: str = payload.get("sid")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username, sid=sid)
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    
    # Session Control: Verify sid matches active_session_id in DB
    if token_data.sid != user.active_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalidated by a more recent login",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return user

async def get_current_active_user(current_user: models.User = Depends(get_current_user)):
    return current_user

async def get_user_from_session(request: Request, db: Session = Depends(database.get_db)) -> Optional[models.User]:
    user_id = request.session.get("user_id")
    sid = request.session.get("sid")
    if not user_id or not sid:
        return None
        
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return None
        
    # Session Control
    if sid != user.active_session_id:
        return None
        
    return user

async def get_optional_user(
    request: Request,
    db: Session = Depends(database.get_db),
    token: str = Depends(oauth2_scheme) # This might force 401 if missing... we need a workaround for pages
):
    # This dependency logic is tricky because oauth2_scheme raises 401.
    # We should probably use a custom dependency or loose checking in routers.
    pass

# Better approach:
# For pages, we use `get_user_from_session`.
# For APIs, we use `get_current_user`.
# Mixed usage:
async def get_current_user_or_none(
    request: Request,
    db: Session = Depends(database.get_db)
):
    # Try session first (cheaper, no crypto decode)
    user = await get_user_from_session(request, db)
    if user:
        return user
        
    # If no session, try header (manual check to avoid 401)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            # Re-use logic or call get_current_user directly?
            # Calling get_current_user requires mocking depends which is hard here.
            # Let's just decode manually.
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            sid: str = payload.get("sid")
            if username:
                user = db.query(models.User).filter(models.User.username == username).first()
                if user and user.active_session_id == sid:
                    return user
        except JWTError:
            pass
            
    return None
