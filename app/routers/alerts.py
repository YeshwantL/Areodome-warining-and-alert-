from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from .. import database, models, schemas, auth

router = APIRouter(
    prefix="/alerts",
    tags=["Alerts"]
)

@router.post("/", response_model=schemas.Alert)
async def create_alert(
    alert: schemas.AlertCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role != models.UserRole.REGIONAL:
        raise HTTPException(status_code=403, detail="Only Regional Airports can create alerts")
    
    new_alert = models.Alert(
        sender_id=current_user.id,
        type=alert.type,
        content=alert.content,
        status=models.AlertStatus.ACTIVE
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)
    return new_alert

@router.get("/active", response_model=List[schemas.Alert])
async def get_active_alerts(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Admin sees all active, Regional sees only their own active? 
    # Requirement: "Regional Airport: Cannot see other airports."
    # So Regional sees own active alerts. Admin sees all.
    
    query = db.query(models.Alert).filter(models.Alert.status == models.AlertStatus.ACTIVE)
    
    if current_user.role == models.UserRole.REGIONAL:
        query = query.filter(models.Alert.sender_id == current_user.id)
        
    return query.all()

@router.post("/{alert_id}/finalize", response_model=schemas.Alert)
async def finalize_alert(
    alert_id: int,
    warning_text: str, # Passed as query param or body? Let's use body if complex, but query is fine for simple string. Better: Body.
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role != models.UserRole.MWO_ADMIN:
        raise HTTPException(status_code=403, detail="Only MWO Admin can finalize alerts")
    
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.status = models.AlertStatus.FINALIZED
    alert.finalized_at = datetime.utcnow()
    alert.final_warning_text = warning_text
    
    db.commit()
    db.refresh(alert)
    return alert
