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
    WWIN81<StationCode><DDHHMM>.a
    Example: WWIN81VASD260000.a
    """
    # DDHHMM
    ddhhmm = timestamp.strftime("%d%H%M")
    return f"WWIN81{station_code}{ddhhmm}.a"

def send_to_ftp(content: str, filename: str) -> dict:
    """
    Sends text content to the configured FTP server using atomic rename.
    1. Uploads to filename.tmp
    2. Renames to final filename
    """
    ftp = None
    tmp_filename = f"{filename}.tmp"
    try:
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT, timeout=10)
        ftp.login(FTP_USER, FTP_PASSWORD)
        
        if FTP_DIRECTORY and FTP_DIRECTORY != "/":
            try:
                ftp.cwd(FTP_DIRECTORY)
            except ftplib.error_perm:
                return {
                    "status": "failure", 
                    "response": f"Directory {FTP_DIRECTORY} does not exist or access denied."
                }

        # Convert string content to BytesIO for upload
        bio = io.BytesIO(content.encode('utf-8'))
        
        # 1. Upload as .tmp
        ftp.storbinary(f'STOR {tmp_filename}', bio)
        
        # 2. Atomic Rename to final .a filename
        try:
            ftp.rename(tmp_filename, filename)
        except ftplib.all_errors as e:
            # Cleanup tmp on rename failure
            try:
                ftp.delete(tmp_filename)
            except:
                pass
            return {
                "status": "failure",
                "response": f"Rename failed: {str(e)}"
            }
        
        return {
            "status": "success",
            "response": "File transferred successfully via atomic rename"
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
