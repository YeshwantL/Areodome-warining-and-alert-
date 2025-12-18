from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from .. import models, database, auth

router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)

class AirportCreate(BaseModel):
    airport_code: str
    airport_name: Optional[str] = None
    password: Optional[str] = None

@router.post("/add_airport")
def add_airport(airport: AirportCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    # 1. Verify Admin
    if current_user.role != models.UserRole.MWO_ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # 2. Logic to add airport
    code = airport.airport_code.upper()
    email = f"{code.lower()}@gmail.com"
    final_password = airport.password if airport.password else "Airport@123"

    # Check if exists
    existing = db.query(models.User).filter(models.User.username == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Airport user already exists")

    new_user = models.User(
        username=email,
        password_hash=auth.get_password_hash(final_password),
        role=models.UserRole.REGIONAL,
        airport_code=code
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": f"Airport {code} added successfully", "username": email}

class StartViewPasswords(BaseModel):
    admin_password: str

@router.post("/view_passwords")
def view_passwords(data: StartViewPasswords, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    # 1. Verify Admin
    if current_user.role != models.UserRole.MWO_ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # 2. Verify Password again
    if not auth.verify_password(data.admin_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect admin password")
    
    # 3. Fetch all regional users
    users = db.query(models.User).filter(models.User.role == models.UserRole.REGIONAL).all()
    
    result = []
    for u in users:
        decrypted = "N/A"
        if u.password_encrypted:
            try:
                decrypted = auth.decrypt_password(u.password_encrypted)
            except Exception:
                decrypted = "Error Decrypting"
        
        result.append({
            "username": u.username,
            "airport_code": u.airport_code,
            "password": decrypted
        })
        
    return result
    return result

@router.get("/airports")
def get_airports(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    if current_user.role != models.UserRole.MWO_ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    users = db.query(models.User).filter(models.User.role == models.UserRole.REGIONAL).all()
    
    # Return list of codes and names (username as name or we can add name field if we had it, strictly we just have code and username)
    # The frontend expects {code, name}
    result = []
    for u in users:
        result.append({
            "code": u.airport_code,
            "name": u.username # Or just code if name unavailable
        })
    return result
