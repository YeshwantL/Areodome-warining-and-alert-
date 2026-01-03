import ftplib
import os
import io
from datetime import datetime

# FTP Configuration (Defaults provided, override with env vars)
FTP_HOST = os.getenv("FTP_HOST", "192.168.101.104")
FTP_PORT = int(os.getenv("FTP_PORT", 21))
FTP_USER = os.getenv("FTP_USER", "admin")  # Placeholder default
FTP_PASSWORD = os.getenv("FTP_PASSWORD", "admin") # Placeholder default
FTP_DIRECTORY = os.getenv("FTP_DIRECTORY", "/")

def generate_filename(station_code: str, serial_number: int, timestamp: datetime) -> str:
    """
    Generates filename according to convention:
    <StationCode>_<SerialNumber>_<Time>_<Date>.txt
    Time format: HHMMSS
    Date format: DDMMYYYY
    """
    time_str = timestamp.strftime("%H%M%S")
    date_str = timestamp.strftime("%d%m%Y")
    return f"{station_code}_{serial_number}_{time_str}_{date_str}.txt"

def send_to_ftp(content: str, filename: str) -> dict:
    """
    Sends text content to the configured FTP server.
    Returns a dictionary with status and response message.
    """
    ftp = None
    try:
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT, timeout=10)
        ftp.login(FTP_USER, FTP_PASSWORD)
        
        if FTP_DIRECTORY and FTP_DIRECTORY != "/":
            try:
                ftp.cwd(FTP_DIRECTORY)
            except ftplib.error_perm:
                # Directory might not exist, try to create it? 
                # For now, let's just log error and return or fail. 
                # Spec doesn't say we need to create it, but safer to error if path is wrong.
                return {
                    "status": "failure", 
                    "response": f"Directory {FTP_DIRECTORY} does not exist or access denied."
                }

        # Convert string content to BytesIO for upload
        bio = io.BytesIO(content.encode('utf-8'))
        
        ftp.storbinary(f'STOR {filename}', bio)
        
        return {
            "status": "success",
            "response": "File transferred successfully"
        }
        
    except ftplib.all_errors as e:
        return {
            "status": "failure",
            "response": str(e)
        }
    finally:
        if ftp:
            try:
                ftp.quit()
            except:
                try:
                    ftp.close()
                except:
                    pass
