from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from .models import UserRole, AlertStatus

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class UserBase(BaseModel):
    username: str
    role: UserRole
    airport_code: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserPasswordChange(BaseModel):
    old_password: str
    new_password: str

class User(UserBase):
    id: int
    class Config:
        orm_mode = True

class AlertBase(BaseModel):
    type: str # "Wind" or "Thunderstorm"
    content: dict

class AlertCreate(AlertBase):
    pass

class Alert(AlertBase):
    id: int
    sender_id: int
    status: AlertStatus
    created_at: datetime
    finalized_at: Optional[datetime] = None
    final_warning_text: Optional[str] = None
    admin_reply: Optional[str] = None
    
    class Config:
        orm_mode = True

class ChatBase(BaseModel):
    receiver_id: int
    message: str

class ChatCreate(ChatBase):
    pass

class Chat(ChatBase):
    id: int
    sender_id: int
    timestamp: datetime

    class Config:
        orm_mode = True
