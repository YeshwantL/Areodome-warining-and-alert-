import socket
import os

TRANSMET_HOST = os.getenv("TRANSMET_HOST", "192.168.101.120")
TRANSMET_PORT = int(os.getenv("TRANSMET_PORT", 10025))

def send_to_transmet(message: str) -> dict:
    """
    Sends a message to the TRANSMET server via TCP.
    Returns a dictionary with status and response.
    """
    try:
        # Create a socket object
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10) # 10 seconds timeout
            s.connect((TRANSMET_HOST, TRANSMET_PORT))
            
            # Send data
            s.sendall(message.encode('utf-8'))
            
            # Receive data
            data = s.recv(1024)
            response = data.decode('utf-8')
            
            return {
                "status": "success",
                "response": response
            }
    except Exception as e:
        return {
            "status": "failure",
            "response": str(e)
        }
