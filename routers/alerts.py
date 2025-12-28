from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from sqlalchemy.sql import func
import database, models, schemas, auth
import transmet
from models import TransmetStatus

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

@router.post("/{alert_id}/reply", response_model=schemas.Alert)
async def reply_alert(
    alert_id: int,
    reply_text: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role != models.UserRole.MWO_ADMIN:
        raise HTTPException(status_code=403, detail="Only MWO Admin can reply to alerts")
    
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.admin_reply = reply_text
    db.commit()
    db.refresh(alert)
    return alert

@router.get("/history", response_model=List[schemas.Alert])
async def get_history(
    start_date: Optional[str] = None, # YYYY-MM-DD
    end_date: Optional[str] = None,   # YYYY-MM-DD
    airport_code: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    query = db.query(models.Alert)
    
    # 1. Join with User to allow filtering by airport_code
    query = query.join(models.User, models.Alert.sender_id == models.User.id)
    
    # 2. Filter by Date Range
    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(models.Alert.created_at >= sd)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    
    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d")
            # Set to end of day
            ed = ed.replace(hour=23, minute=59, second=59)
            query = query.filter(models.Alert.created_at <= ed)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    if not start_date and not end_date:
        # Default: Last 30 days if no range specified
        from datetime import timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        query = query.filter(models.Alert.created_at >= thirty_days_ago)

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

@router.post("/{alert_id}/transmit", response_model=schemas.Alert)
async def transmit_alert(
    alert_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role != models.UserRole.MWO_ADMIN:
        raise HTTPException(status_code=403, detail="Only MWO Admin can transmit alerts")
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    if alert.status != models.AlertStatus.FINALIZED:
        raise HTTPException(status_code=400, detail="Only finalized alerts can be transmitted")
    
    if not alert.final_warning_text:
         raise HTTPException(status_code=400, detail="Final warning text is missing")

    # Send to TRANSMET
    result = transmet.send_to_transmet(alert.final_warning_text)
    
    if result["status"] == "success":
        alert.transmet_status = TransmetStatus.SUCCESS
        alert.transmet_response = result["response"]
    else:
        alert.transmet_status = TransmetStatus.FAILURE
        alert.transmet_response = result["response"]
        
    db.commit()
    db.refresh(alert)
    return alert

@router.get("/history/download")
async def download_history(
    start_date: Optional[str] = None, # YYYY-MM-DD
    end_date: Optional[str] = None,   # YYYY-MM-DD
    airport_code: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    from fastapi.responses import StreamingResponse
    import io

    query = db.query(models.Alert).join(models.User, models.Alert.sender_id == models.User.id)

    # 1. Access Control
    if current_user.role == models.UserRole.REGIONAL:
        query = query.filter(models.Alert.sender_id == current_user.id)
    elif current_user.role == models.UserRole.MWO_ADMIN:
        if airport_code:
            query = query.filter(models.User.airport_code == airport_code)

    # 2. Date Range Filtering
    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(models.Alert.created_at >= sd)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d")
            # Set to end of day
            ed = ed.replace(hour=23, minute=59, second=59)
            query = query.filter(models.Alert.created_at <= ed)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    alerts = query.order_by(models.Alert.created_at.desc()).all()

    # 3. Generate Text Content
    output = io.StringIO()
    output.write(f"--- AERODROME WARNING HISTORY REPORT ---\n")
    output.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.write(f"Period: {start_date or 'Start'} to {end_date or 'End'}\n")
    output.write(f"Airport Filter: {airport_code or 'All'}\n")
    output.write("-" * 50 + "\n\n")

    if not alerts:
        output.write("No alerts found for the selected criteria.\n")
    else:
        for idx, alert in enumerate(alerts, 1):
            airport = alert.sender.airport_code or "Unknown"
            timestamp = alert.created_at.strftime('%Y-%m-%d %H:%M:%S')
            
            output.write(f"[{idx}] STATION: {airport}\n")
            output.write(f"    TIME: {timestamp}\n")
            output.write(f"    TYPE: {alert.type.upper()}\n")
            output.write(f"    STATUS: {alert.status.value.upper()}\n")
            
            if alert.final_warning_text:
                output.write(f"    WARNING TEXT:\n    {alert.final_warning_text}\n")
            elif alert.content and 'generated_text' in alert.content:
                output.write(f"    PREVIEW TEXT:\n    {alert.content['generated_text']}\n")
            else:
                # Handle dictionary representation
                content_str = str(alert.content)
                output.write(f"    CONTENT: {content_str}\n")
                
            if alert.admin_reply:
                output.write(f"    ADMIN REPLY: {alert.admin_reply}\n")
                
            output.write("-" * 30 + "\n")

    output.seek(0)
    
    filename = f"alert_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
