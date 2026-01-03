import sys
import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from sqlalchemy.sql import func

# Allow standalone execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

import ftp_client

@router.post("/{alert_id}/finalize", response_model=schemas.Alert)
async def finalize_alert(
    alert_id: int,
    data: schemas.AlertFinalize,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role != models.UserRole.MWO_ADMIN:
        raise HTTPException(status_code=403, detail="Only MWO Admin can finalize alerts")
    
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # 1. Update status and content
    alert.status = models.AlertStatus.FINALIZED
    alert.finalized_at = datetime.utcnow()
    alert.final_warning_text = data.warning_text
    
    # 2. Assign Serial Number (Per Airport)
    # Get the user (sender) to check airport code/id
    # We assume one user per airport or strictly filter by sender_id for now 
    # as per requirement to increment per airport.
    max_serial = db.query(func.max(models.Alert.serial_number)).filter(
        models.Alert.sender_id == alert.sender_id
    ).scalar() or 0
    
    next_serial = max_serial + 1
    alert.serial_number = next_serial
    
    # Commit first to lock in serial number and finalization
    db.commit()
    db.refresh(alert)
    
    # 3. Transmit to FTP
    try:
        # User <StationCode> from sender's airport_code
        station_code = alert.sender.airport_code or "UNKNOWN"
        filename = ftp_client.generate_filename(station_code, next_serial, alert.finalized_at)
        
        # Determine status
        alert.ftp_status = models.FtpStatus.PENDING
        
        # Send
        result = ftp_client.send_to_ftp(alert.final_warning_text, filename)
        
        if result["status"] == "success":
             alert.ftp_status = models.FtpStatus.SUCCESS
        else:
             alert.ftp_status = models.FtpStatus.FAILURE
             
        alert.ftp_response = result["response"]
        
    except Exception as e:
        alert.ftp_status = models.FtpStatus.FAILURE
        alert.ftp_response = f"Internal Error: {str(e)}"
    
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

    def format_aviation_warning(alert):
        """
        Generates standard aviation warning string:
        VAKP 031200 AD WRNG 1 VALID 031200/031800 SFC WSPD 17KT MAX27 FROM 292 DEG FCST NC=
        """
        try:
            # 1. Station and Time
            station = alert.sender.airport_code or "XXXX"
            dt = alert.created_at
            ddhhmm = dt.strftime("%d%H%M")
            
            # 2. Serial Number
            serial = alert.serial_number or "X"
            
            # 3. Validity (Default 4 hours if not in content)
            valid_from = dt
            valid_to = dt + timedelta(hours=4) # Default
            # Check content for validity duration? For now default.
            valid_str = f"{valid_from.strftime('%d%H%M')}/{valid_to.strftime('%d%H%M')}"
            
            # 4. Met Details
            content_parts = []
            if alert.content:
                if alert.type == "Wind":
                    speed = alert.content.get('speed')
                    gust = alert.content.get('gust')
                    direction = alert.content.get('direction')
                    
                    if speed: content_parts.append(f"SFC WSPD {speed}KT")
                    if gust: content_parts.append(f"MAX{gust}") # Image shows MAX27 (no KT?) Image says MAX27. Let's assume.
                    if direction: content_parts.append(f"FROM {direction} DEG")
                elif alert.type == "Thunderstorm":
                    content_parts.append("TS")
                    # Add other TS details if available
            
            details = " ".join(content_parts)
            
            return f"{station} {ddhhmm} AD WRNG {serial} VALID {valid_str} {details} FCST NC="
            
        except Exception:
            return "Error generating format"

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
            
            # Always use the standardized aviation format for the report
            message = format_aviation_warning(alert)
            output.write(f"    WARNING TEXT:\n    {message}\n")
            
            # If there was a manual final text that differs significantly, we could append it,
            # but the user specifically requested the "proper" format (constructed).
            
            # (Optional: If existing final text is not just "okk" or similar, maybe strictly we should keep it,
            # but for this request, strict format is priority).
            if alert.final_warning_text and alert.final_warning_text != message:
                # Check if it looks like a manual note
                if len(alert.final_warning_text) < 20 or "valid" not in alert.final_warning_text.lower():
                     output.write(f"    OPERATOR NOTE: {alert.final_warning_text}\n")
                
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
