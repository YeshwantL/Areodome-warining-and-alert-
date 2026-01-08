import sys
import os
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.sql import func

# Allow standalone execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database, models, schemas, auth
import transmet
from models import TransmetStatus

def format_aviation_warning(alert):
    """
    Generates standard aviation warning string:
    VAKP 031200 AD WRNG 1 VALID 031200/031800 SFC WSPD 17KT MAX27 FROM 292 DEG FCST NC=
    """
    try:
        # 0. Prefer pre-generated text from frontend if available (Exact Match)
        if alert.content and isinstance(alert.content, dict) and alert.content.get("generated_text"):
            return alert.content.get("generated_text")

        # 1. Station and Time
        station = alert.sender.airport_code or "XXXX"
        dt = alert.created_at
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
        # Ensure the aviation format always starts with the station/time and prepend WWIN81 if missing
        raw_format = f"{station} {ddhhmm} AD WRNG {serial} VALID {valid_str} {details} FCST NC="
        if not raw_format.startswith("WWIN81"):
            return f"WWIN81 {raw_format}"
        return raw_format
        
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
        
        # Header: WWIN81 <StationCode> <DDHHMM>
        ddhhmm = alert.finalized_at.strftime("%d%H%M")
        header = f"WWIN81 {station_code} {ddhhmm}"
        file_content = f"{header}\n{alert.final_warning_text}"
        
        # Send
        result = ftp_client.send_to_ftp(file_content, filename)
        
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

    # Initialize result for safety
    result = {"status": "failure", "response": "Transmission not attempted"}
        
    # Generate .a file for passed warnings
    try:
        station_code = alert.sender.airport_code or "XXXX"
        dt = alert.finalized_at or datetime.utcnow()
        ddhhmm = dt.strftime("%d%H%M")
        header_line = f"WWIN81 {station_code} {ddhhmm}"
        
        # Avoid duplicating the header if it's already in the final_warning_text
        body = alert.final_warning_text
        if body.startswith(header_line):
            file_content = body
        else:
            file_content = f"{header_line}\n{body}"
        
        # Socket transmission content must match the file content
        transmet_payload = file_content
        
        # Actually send the FULL formatted content to Socket
        result = transmet.send_to_transmet(transmet_payload)
        
        # Filename: WWIN81<StationCode><DDHHMM>.a
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
        time_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        if airport_code:
            filename = f"WWIN81{airport_code}_{time_str}.txt"
        else:
            filename = f"WWIN81_HISTORY_{time_str}.txt"
            
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
                
                # Filename: WWIN81<Station><DDHHMM>_<ID>.a to avoid duplicate names in zip
                filename = f"WWIN81{station_code}{ddhhmm}_{alert.id}.a"
                header_line = f"WWIN81 {station_code} {ddhhmm}"
                
                body = alert.final_warning_text or ""
                if not body.startswith("WWIN81"):
                    content = f"{header_line}\n{body}"
                else:
                    content = body
                
                zip_file.writestr(filename, content)

        zip_buffer.seek(0)
        zip_filename = f"alerts_bulk_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
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
        header_line = f"WWIN81 {station_code} {ddhhmm}"
        
        filename = f"WWIN81{station_code}{ddhhmm}.a"
        body = alert.final_warning_text
        if body.startswith(header_line):
            content = body
        else:
            content = f"{header_line}\n{body}"
        
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
