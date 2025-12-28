"""
DATABASE MODELS
Contains SQLAlchemy models for Users, Alerts, and Chats.
NOTE: This is NOT the wind prediction file (which is model.py).
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from database import Base

class UserRole(str, enum.Enum):
    REGIONAL = "regional_airport"
    MWO_ADMIN = "mwo_admin"

class AlertStatus(str, enum.Enum):
    ACTIVE = "active"
    FINALIZED = "finalized"
    ARCHIVED = "archived"

class TransmetStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILURE = "failure"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String, nullable=True)
    password_hash = Column(String)
    password_encrypted = Column(String, nullable=True) # For Admin recovery/view
    role = Column(Enum(UserRole))
    airport_code = Column(String, nullable=True) # e.g., VABB, VOMM. Null for Admin if generic.
    active_session_id = Column(String, nullable=True) # For single active session control

    alerts = relationship("Alert", back_populates="sender")
    sent_chats = relationship("Chat", foreign_keys="[Chat.sender_id]", back_populates="sender")
    received_chats = relationship("Chat", foreign_keys="[Chat.receiver_id]", back_populates="receiver")

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String) # Wind, Thunderstorm
    content = Column(JSON) # Stores specific fields like speed, gust, etc.
    status = Column(Enum(AlertStatus), default=AlertStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    
    # For finalized warning text
    final_warning_text = Column(String, nullable=True)
    
    # Admin Reply
    admin_reply = Column(String, nullable=True)

    # TRANSMET Status
    transmet_status = Column(Enum(TransmetStatus), nullable=True, default=None)
    transmet_response = Column(String, nullable=True)

    sender = relationship("User", back_populates="alerts")

class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    receiver_id = Column(Integer, ForeignKey("users.id"))
    message = Column(String)
    is_read = Column(Boolean, default=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_chats")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_chats")
