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
