import sys
import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

# Allow standalone execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database, models, schemas, auth

router = APIRouter(tags=["Authentication"])

@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    import uuid
    new_sid = str(uuid.uuid4())
    user.active_session_id = new_sid
    db.commit()

    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role.value, "id": user.id, "sid": new_sid}, 
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    return current_user

@router.get("/admin-info")
def get_admin_info(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    # Find the MWO Admin (Assuming there is at least one, taking the first generic one or any)
    admin = db.query(models.User).filter(models.User.role == models.UserRole.MWO_ADMIN).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    return {
        "id": admin.id,
        "username": admin.username,
        "airport_code": admin.airport_code
    }

@router.post("/change-password")
async def change_password(
    password_data: schemas.UserPasswordChange,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(database.get_db)
):
    if not auth.verify_password(password_data.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password"
        )
    
    current_user.password_hash = auth.get_password_hash(password_data.new_password)
    current_user.password_encrypted = auth.encrypt_password(password_data.new_password)
    
    # Notify Admin (ID 1)
    # Check if admin exists first to avoid error? Assuming ID 1 is mwo_admin from seed.
    admin_user = db.query(models.User).filter(models.User.role == models.UserRole.MWO_ADMIN).first()
    if admin_user and admin_user.id != current_user.id:
        notification_msg = f"User {current_user.username} has changed their password."
        new_chat = models.Chat(
            sender_id=current_user.id,
            receiver_id=admin_user.id,
            message=notification_msg
        )
        db.add(new_chat)

    db.commit()
    return {"message": "Password changed successfully"}
