import sys
import os
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.sql import func

# Allow standalone execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database, models, schemas, auth
import transmet
from models import TransmetStatus
import re

def parse_validity_from_text(text: str) -> Optional[datetime]:
    """
    Parses VALID DDHHMM/DDHHMM or VALID DDHHMM from text and returns the end time as a UTC datetime.
    Supports Z suffix, HHMM only (today default), and month rollover logic.
    """
    if not text:
        return None
        
    # Use word boundary to avoid matching "Validated"
    # Try Range first: VALID 160630/161030 or VALID 0630/1030
    range_match = re.search(r'\bVALID\s+(\d{4,6})Z?\s*/\s*(\d{4,6})Z?', text, re.IGNORECASE)
    if range_match:
        try:
            end_val = range_match.group(2)
            return _parse_aviation_time(end_val)
        except Exception:
            return None

    # Try Single: VALID 161030 or VALID 1030
    single_match = re.search(r'\bVALID\s+(\d{4,6})Z?', text, re.IGNORECASE)
    if single_match:
        try:
            end_val = single_match.group(1)
            return _parse_aviation_time(end_val)
        except Exception:
            return None
            
    return None

def _parse_aviation_time(val: str) -> Optional[datetime]:
    if len(val) == 6:
        # DDHHMM
        day, hour, minute = int(val[:2]), int(val[2:4]), int(val[4:])
        return _contextualize_expiry(day, hour, minute)
    elif len(val) == 4:
        # HHMM (assume today UTC)
        now = datetime.utcnow()
        hour, minute = int(val[:2]), int(val[2:])
        return _contextualize_expiry(now.day, hour, minute)
    return None

def _contextualize_expiry(end_day: int, end_hour: int, end_min: int) -> datetime:
    now = datetime.utcnow()
    # Assume current year and month for the end time
    expiry = now.replace(day=end_day, hour=end_hour, minute=end_min, second=0, microsecond=0)
    
    # Month rollover logic
    if expiry < now - timedelta(days=15):
        if expiry.month == 12:
            expiry = expiry.replace(year=expiry.year + 1, month=1)
        else:
            expiry = expiry.replace(month=expiry.month + 1)
    elif expiry > now + timedelta(days=15):
        if expiry.month == 1:
            expiry = expiry.replace(year=expiry.year - 1, month=12)
        else:
            expiry = expiry.replace(month=expiry.month - 1)
            
    return expiry

def format_aviation_warning(alert):
    """
    Generates standard aviation warning string:
    WWIN81 VAKP 170650
    VAKP 170650 AD WRNG 1 VALID 170650/171050 SFC WSPD 17KT MAX27 FROM 090 DEG FCST NC=
    """
    try:
        # 0. Prefer pre-generated text from frontend if available (Exact Match)
        if alert.content and isinstance(alert.content, dict) and alert.content.get("generated_text"):
            return alert.content.get("generated_text")

        # 1. Station and Time
        station = alert.sender.airport_code or "XXXX"
        dt = alert.created_at or datetime.utcnow()
        ddhhmm = dt.strftime("%d%H%M")
        
        # 2. Serial Number
        serial = alert.serial_number or "X"
        
        # 3. Validity (Default 4 hours if not in content)
        valid_from = dt
        valid_to = dt + timedelta(hours=4) # Default
        valid_str = f"{valid_from.strftime('%d%H%M')}/{valid_to.strftime('%d%H%M')}"
        
        # 4. Met Details
        content_parts = []
        if alert.content:
            if alert.type == "Wind":
                speed = alert.content.get('speed')
                gust = alert.content.get('gust')
                direction = alert.content.get('direction')
                
                if speed: content_parts.append(f"SFC WSPD {speed}KT")
                if gust: content_parts.append(f"MAX{gust}")
                if direction: content_parts.append(f"FROM {direction} DEG")
            elif alert.type == "Thunderstorm":
                content_parts.append("TS")
        
        details = " ".join(content_parts)
        
        # New format: WWIN81 STATION DDHHMM on first line, 
        # then STATION DDHHMM on second line, then warning on third line
        warning_line = f"AD WRNG {serial} VALID {valid_str} {details} FCST NC="
        return f"WWIN81 {station_code} {ddhhmm}\n{station_code} {ddhhmm}\n{warning_line}"
        
    except Exception as e:
        return f"Error generating format: {str(e)}"

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
    
    
    # Parse validity from generated text if present
    gen_text = alert.content.get('generated_text', '')
    parsed_valid_until = parse_validity_from_text(gen_text)
    if parsed_valid_until:
        alert.content['valid_until_iso'] = parsed_valid_until.isoformat() + "Z"
    else:
        # Fallback to manual date calc if parsing fails, but user wants parsing to be primary.
        # If parsing fails, we might want to store 'INVALID' or something, 
        # but let's see how create_alert handles valid_to.
        valid_to_str = alert.content.get('valid_to', '')
        if valid_to_str and len(valid_to_str) == 4:
            now_utc = datetime.utcnow()
            try:
                hour = int(valid_to_str[:2])
                minute = int(valid_to_str[2:])
                valid_until = now_utc.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if valid_until < now_utc:
                     valid_until += timedelta(days=1)
                alert.content['valid_until_iso'] = valid_until.isoformat() + "Z"
            except ValueError:
                pass

    new_alert = models.Alert(
        sender_id=current_user.id,
        type=alert.type,
        content=alert.content,
        status=models.AlertStatus.ACTIVE,
        created_at=datetime.utcnow() # Explicit UTC
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
    
    # Filter by Expiry
    # We need to fetch into python to parse the JSON content field or use a custom filter if supported DB wise.
    # JSON filtering in SQLite/Postgres varies. Python filtering is safer for now given low volume.
    
    query = db.query(models.Alert).filter(
        models.Alert.status.in_([models.AlertStatus.ACTIVE, models.AlertStatus.FINALIZED])
    )
    
    if current_user.role == models.UserRole.REGIONAL:
        query = query.filter(models.Alert.sender_id == current_user.id)
        
    all_active = query.all()
    
    valid_alerts = []
    now_utc = datetime.now(timezone.utc)
    
    for alert in all_active:
        # Check expiry
        if alert.content and isinstance(alert.content, dict):
            valid_until_iso = alert.content.get('valid_until_iso')
            if valid_until_iso:
                try:
                    valid_until = datetime.fromisoformat(valid_until_iso)
                    if valid_until.tzinfo is None:
                        valid_until = valid_until.replace(tzinfo=timezone.utc)
                    # If expired, mark as ARCHIVED/FINALIZED? 
                    # User said: "automatically removed or marked inactive once validity period expires."
                    # We will filter it out from display. Opt: Update status in DB for cleanup.
                    if now_utc > valid_until:
                        # Auto-expire
                        # alert.status = models.AlertStatus.ARCHIVED # Optimistic update?
                        # db.commit() # Side effect in GET? safer to just filter for view.
                        continue
                except ValueError:
                    pass
        
        # Populate station_code for frontend
        if alert.sender:
             alert.station_code = alert.sender.airport_code
             
        valid_alerts.append(alert)
        
    return valid_alerts



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
    
    # 3. Transmit to FTP and Airport System (Transmet)
    try:
        station_code = alert.sender.airport_code or "UNKNOWN"
        filename = ftp_client.generate_filename(station_code, next_serial, alert.finalized_at)

        # Prepare content
        # Ensure WWIN81 header format: WWIN81 STATION DDHHMM
        body = alert.final_warning_text
        station_code = alert.sender.airport_code or "XXXX"
        dt = alert.finalized_at or datetime.utcnow()
        ddhhmm = dt.strftime("%d%H%M")
        
        if body.startswith("WWIN81"):
            lines = body.splitlines()
            if lines and not lines[0].strip().endswith(".X"):
                lines[0] = lines[0].strip() + " .X"
                file_content = "\n".join(lines)
            else:
                file_content = body
        else:
            file_content = f"WWIN81 {station_code} {ddhhmm} .X\n{body}"
        
        # A. Delivery via FTP - DISABLED due to requirement "warning should not go to any other server"
        # alert.ftp_status = models.FtpStatus.PENDING
        # ftp_result = ftp_client.send_to_ftp(file_content, filename)
        # 
        # if ftp_result["status"] == "success":
        #      alert.ftp_status = models.FtpStatus.SUCCESS
        # else:
        #      alert.ftp_status = models.FtpStatus.FAILURE
        # alert.ftp_response = ftp_result["response"]
        
        # Explicitly mark as skipped/failure to indicate it wasn't sent, or just log it.
        # Check if 'DISABLED' status exists or usage FAILURE. Using a placeholder response.
        alert.ftp_status = models.FtpStatus.FAILURE # Or new status if available, but FAILURE/SKIPPED is safe
        alert.ftp_response = "FTP Disabled by configuration"

        # B. Delivery to Airport System (Transmet/Socket)
        alert.transmet_status = models.TransmetStatus.PENDING
        transmet_result = transmet.send_to_transmet(file_content)
        
        if transmet_result["status"] == "success":
            alert.transmet_status = models.TransmetStatus.SUCCESS
        else:
            alert.transmet_status = models.TransmetStatus.FAILURE
        alert.transmet_response = transmet_result["response"]

        # C. Local backup (optional but good for audit)
        os.makedirs("transmitted_warnings", exist_ok=True)
        local_path = os.path.join("transmitted_warnings", filename)
        with open(local_path, "w") as f:
            f.write(file_content)
             
    except Exception as e:
        if not alert.ftp_status: alert.ftp_status = models.FtpStatus.FAILURE
        if not alert.transmet_status: alert.transmet_status = models.TransmetStatus.FAILURE
        error_msg = f"Delivery Error: {str(e)}"
        alert.ftp_response = alert.ftp_response or error_msg
        alert.transmet_response = alert.transmet_response or error_msg
    
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

    return alert

# NEW ENDPOINTS FOR EDIT / CONFIRM

@router.post("/{alert_id}/edit", response_model=schemas.Alert)
async def update_alert_text(
    alert_id: int,
    data: schemas.AlertFinalize, # Reusing simple text wrapper
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role != models.UserRole.MWO_ADMIN:
        raise HTTPException(status_code=403, detail="Only MWO Admin can edit alerts")
        
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    # Re-parse validity whenever text is edited
    parsed_valid_until = parse_validity_from_text(data.warning_text)
    
    # Update text
    alert.final_warning_text = data.warning_text
    
    # Also update content generated text to stay in sync?
    if alert.content and isinstance(alert.content, dict):
        new_content = alert.content.copy()
        new_content['generated_text'] = data.warning_text
        if parsed_valid_until:
             new_content['valid_until_iso'] = parsed_valid_until.isoformat() + "Z"
        else:
             # If parsing fails on edit, we might want to clear it? 
             # Or mark it invalid. Let's clear it so UI shows "Invalid"
             new_content['valid_until_iso'] = None
        alert.content = new_content
        
    db.commit()
    db.refresh(alert)
    return alert

@router.post("/{alert_id}/confirm", response_model=schemas.Alert)
async def confirm_alert(
    alert_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role != models.UserRole.MWO_ADMIN:
        raise HTTPException(status_code=403, detail="Only MWO Admin can confirm alerts")
    
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # If first time confirming/finalizing, generate serial number?
    if not alert.finalized_at:
        alert.finalized_at = datetime.utcnow()
        # Generate Serial
        max_serial = db.query(func.max(models.Alert.serial_number)).filter(
            models.Alert.sender_id == alert.sender_id
        ).scalar() or 0
        alert.serial_number = max_serial + 1
        
    # Re-parse validity from currently confirmed text just in case
    current_text = alert.final_warning_text or (alert.content.get('generated_text') if alert.content else None)
    parsed_valid_until = parse_validity_from_text(current_text)
    if parsed_valid_until and alert.content:
        new_content = alert.content.copy()
        new_content['valid_until_iso'] = parsed_valid_until.isoformat()
        alert.content = new_content
        
    # Set status to FINALIZED so it is locked, but it will still show in active list until expiry
    alert.status = models.AlertStatus.FINALIZED
    
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
    
    # Use final text if confirmed, else fallback to generated text
    body = alert.final_warning_text
    if not body and alert.content:
        body = alert.content.get('generated_text')
        
    if not body:
         raise HTTPException(status_code=400, detail="Final warning text is missing")
    
    # Check if confirmed (finalized_at set) OR if we allow transmitting unconfirmed?
    # User requirement: "Only current version... warning must be sent"
    # Logic: If it has text, we can transmit. It keeps status same.
    
    # Initialize result for safety
    result = {"status": "failure", "response": "Transmission not attempted"}
        
    # Generate .a file for passed warnings
    try:
        # Prepare content
        # body is already set above
        station_code = alert.sender.airport_code or "XXXX"
        dt = alert.finalized_at or datetime.utcnow()
        ddhhmm = dt.strftime("%d%H%M")
        
        if body.startswith("WWIN81"):
            lines = body.splitlines()
            if lines and not lines[0].strip().endswith(".X"):
                lines[0] = lines[0].strip() + " .X"
                file_content = "\n".join(lines)
            else:
                file_content = body
        else:
            file_content = f"WWIN81 {station_code} {ddhhmm} .X\n{body}"
        
        # Socket transmission content must match the file content
        transmet_payload = file_content
        
        # Actually send the FULL formatted content to Socket
        result = transmet.send_to_transmet(transmet_payload)
        
        # Filename: WWIN81<StationCode><DDHHMM>.a
        station_code = alert.sender.airport_code or "XXXX"
        dt = alert.finalized_at or datetime.utcnow()
        ddhhmm = dt.strftime("%d%H%M")
        filename_base = f"WWIN81{station_code}{ddhhmm}.a"
        file_path = os.path.join("transmitted_warnings", filename_base)
        
        # Ensure dir exists (redundant if mkdir run, but safe)
        os.makedirs("transmitted_warnings", exist_ok=True)
        
        with open(file_path, "w") as f:
            f.write(file_content)
            
    except Exception as e:
        print(f"Error during dissemination: {e}")
        # Non-blocking error, result keeps its status

        
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
    import io
    
    try:
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

        if not alerts:
            output.write("NO FINALIZED ALERTS FOUND FOR SELECTION\n")
        else:
            for alert in alerts:
                message = format_aviation_warning(alert)
                output.write(f"{message}\n\n")

        output.seek(0)
        
        # 4. Filename Standardization
        time_str = datetime.now().strftime('%d%H%M')
        if airport_code:
            filename = f"WWIN81{airport_code}{time_str}.txt"
        else:
            filename = f"WWIN81{time_str}.txt"
            
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@router.get("/history/download/bulk_a")
async def download_history_bulk_a(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    airport_code: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    import zipfile
    import io
    
    try:
        query = db.query(models.Alert).join(models.User, models.Alert.sender_id == models.User.id)
        query = query.filter(models.Alert.status == models.AlertStatus.FINALIZED)

        if current_user.role == models.UserRole.REGIONAL:
            query = query.filter(models.Alert.sender_id == current_user.id)
        elif current_user.role == models.UserRole.MWO_ADMIN and airport_code:
            query = query.filter(models.User.airport_code == airport_code)

        if start_date:
            try:
                sd = datetime.strptime(start_date, "%Y-%m-%d")
                query = query.filter(models.Alert.created_at >= sd)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date")
        if end_date:
            try:
                ed = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                query = query.filter(models.Alert.created_at <= ed)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date")

        alerts = query.order_by(models.Alert.created_at.desc()).all()
        if not alerts:
            raise HTTPException(status_code=404, detail="No finalized alerts found for selection")

        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for alert in alerts:
                station_code = alert.sender.airport_code or "XXXX"
                dt = alert.finalized_at or alert.created_at
                ddhhmm = dt.strftime("%d%H%M")
                
                # Filename: WWIN81<Station><DDHHMM><ID>.a to avoid duplicate names in zip
                filename = f"WWIN81{station_code}{ddhhmm}{alert.id}.a"
                
                body = alert.final_warning_text or ""
                if body.startswith("WWIN81"):
                    content = body
                else:
                    content = f"WWIN81 {station_code} {ddhhmm}\n{body}"
                
                zip_file.writestr(filename, content)

        zip_buffer.seek(0)
        zip_filename = f"alertsbulk{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk download failed: {str(e)}")

@router.get("/{alert_id}/download")
async def download_alert(
    alert_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    try:
        alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
        if not alert or alert.status != models.AlertStatus.FINALIZED:
            raise HTTPException(status_code=404, detail="Finalized alert not found")
            
        station_code = alert.sender.airport_code or "XXXX"
        dt = alert.finalized_at or datetime.utcnow()
        ddhhmm = dt.strftime("%d%H%M")
        
        filename = f"WWIN81{station_code}{ddhhmm}.a"
        body = alert.final_warning_text
        if body.startswith("WWIN81"):
            content = body
        else:
            content = f"WWIN81 {station_code} {ddhhmm}\n{body}"
        
        return Response(
            content=content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")