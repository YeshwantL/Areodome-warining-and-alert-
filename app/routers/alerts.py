from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from sqlalchemy.sql import func
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
    db.commit()
    db.refresh(alert)
    return alert

    alert.admin_reply = reply_text
    db.commit()
    db.refresh(alert)
    return alert

@router.get("/history", response_model=List[schemas.Alert])
async def get_history(
    date: Optional[str] = None, # YYYY-MM-DD
    month: Optional[str] = None, # YYYY-MM
    airport_code: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    query = db.query(models.Alert)
    
    # 1. Join with User to allow filtering by airport_code
    query = query.join(models.User, models.Alert.sender_id == models.User.id)
    
    # 2. Filter by Date or Month
    if date:
        # Assuming date is YYYY-MM-DD
        try:
            query_date = datetime.strptime(date, "%Y-%m-%d").date()
            # Filter where created_at matches this date
            # SQLite specific, but standard enough:
            # We can use cast to date or compare ranges. Range is safer.
            start_of_day = datetime(query_date.year, query_date.month, query_date.day, 0, 0, 0)
            end_of_day = datetime(query_date.year, query_date.month, query_date.day, 23, 59, 59)
            query = query.filter(models.Alert.created_at >= start_of_day, models.Alert.created_at <= end_of_day)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    elif month:
        # Assuming month is YYYY-MM
        try:
            year, m = map(int, month.split('-'))
            # Filter by month
            # Using extract
            from sqlalchemy import extract
            query = query.filter(extract('year', models.Alert.created_at) == year)
            query = query.filter(extract('month', models.Alert.created_at) == m)
        except ValueError:
             raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")
    else:
        # Default: Last 6 months? Or all? Plan said default 6 months.
        # Let's import timedelta
        from datetime import timedelta
        six_months_ago = datetime.utcnow() - timedelta(days=180)
        query = query.filter(models.Alert.created_at >= six_months_ago)

    # 3. Role Based Access
    if current_user.role == models.UserRole.REGIONAL:
        # Can only see own alerts
        query = query.filter(models.Alert.sender_id == current_user.id)
        # Note: Regional cannot filter by airport_code (it's redundant or forbidden)
    elif current_user.role == models.UserRole.MWO_ADMIN:
        # Can see all, can filter by airport_code
        if airport_code:
             query = query.filter(models.User.airport_code == airport_code)

    # Order by newest first
    query = query.order_by(models.Alert.created_at.desc())
    
    return query.all()
