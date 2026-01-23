from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from models import UserRole, AlertStatus, TransmetStatus, FtpStatus

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    id: Optional[int] = None
    sid: Optional[str] = None

class UserBase(BaseModel):
    username: str
    full_name: Optional[str] = None
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
        from_attributes = True

class AlertBase(BaseModel):
    type: str # "Wind" or "Thunderstorm"
    content: dict

class AlertCreate(AlertBase):
    pass

class AlertFinalize(BaseModel):
    warning_text: str

class Alert(AlertBase):
    id: int
    sender_id: int
    status: AlertStatus
    created_at: datetime
    finalized_at: Optional[datetime] = None
    final_warning_text: Optional[str] = None
    admin_reply: Optional[str] = None
    transmet_status: Optional[TransmetStatus] = None
    transmet_response: Optional[str] = None
    
    serial_number: Optional[int] = None
    ftp_status: Optional[FtpStatus] = None
    ftp_response: Optional[str] = None
    station_code: Optional[str] = None
    
    class Config:
        from_attributes = True

class ChatBase(BaseModel):
    receiver_id: int
    message: str

class ChatCreate(ChatBase):
    pass

class Chat(ChatBase):
    id: int
    sender_id: Optional[int] = None
    is_read: bool = False
    timestamp: datetime

    class Config:
        from_attributes = True
