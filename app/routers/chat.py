from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List
from .. import database, models, schemas, auth

router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)

@router.post("/", response_model=schemas.Chat)
async def send_message(
    chat: schemas.ChatCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Validation:
    # Regional can only send to Admin (or specific Admin ID if we had multiple, but let's assume Admin ID is known or looked up).
    # Actually, the schema has receiver_id.
    
    receiver = db.query(models.User).filter(models.User.id == chat.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found")

    if current_user.role == models.UserRole.REGIONAL:
        if receiver.role != models.UserRole.MWO_ADMIN:
            raise HTTPException(status_code=403, detail="Regional airports can only chat with MWO Mumbai")
    
    # Admin can send to anyone.

    new_chat = models.Chat(
        sender_id=current_user.id,
        receiver_id=chat.receiver_id,
        message=chat.message
    )
    db.add(new_chat)
    db.commit()
    db.refresh(new_chat)
    return new_chat

@router.get("/{partner_id}", response_model=List[schemas.Chat])
async def get_chat_history(
    partner_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Verify partner exists
    partner = db.query(models.User).filter(models.User.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="User not found")

    # Access Control
    if current_user.role == models.UserRole.REGIONAL:
        if partner.role != models.UserRole.MWO_ADMIN:
            raise HTTPException(status_code=403, detail="Regional airports can only access chat with MWO Mumbai")
        # Ensure they are not trying to view chat between Admin and ANOTHER airport (though partner_id implies direct chat)
        # If I am Regional, I can only see chat where I am sender or receiver, AND partner is Admin.
    
    # Query: (Sender=Me AND Receiver=Partner) OR (Sender=Partner AND Receiver=Me)
    chats = db.query(models.Chat).filter(
        or_(
            and_(models.Chat.sender_id == current_user.id, models.Chat.receiver_id == partner_id),
            and_(models.Chat.sender_id == partner_id, models.Chat.receiver_id == current_user.id)
        )
    ).order_by(models.Chat.timestamp.asc()).all()
    
    return chats
