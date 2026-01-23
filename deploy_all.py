import paramiko
import os
import time

HOSTNAME = "121.240.10.8"
USERNAME = "mwomumbai"
PASSWORD = "mwomumbai@4321"

def deploy_full():
    print(f"Connecting to {HOSTNAME}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(HOSTNAME, username=USERNAME, password=PASSWORD)
        print("Connected successfully.")
        
        project_dir = "./app" 
        
        files_to_upload = [
            "main.py",
            "routers/alerts.py",
            "routers/authentication.py",
            "routers/prediction.py",
            "fetch_data.py",
            "ftp_client.py",
            "static/dashboard.js",
            "templates/dashboard.html",
            "parse_metar.py",
            "model.py",
            "wind_prediction.py",
            "transmet.py"
        ]
        
        # 1. Handle old auth router cleanup and unnecessary scripts
        print("Cleaning up old files and scripts on server...")
        files_to_remove = [
            "routers/auth.py",
            "debug_calm_wind.py",
            "test_actual_predictions.py",
            "test_filename_format.py",
            "test_meteorological.py",
            "test_prediction_flow.py",
            "test_warning_format.py",
            "test_wind_logic.py",
            "test_wwin81_format.py",
            "verify_admin_features.py",
            "verify_direction_fix.py",
            "verify_formulas.py",
            "verify_history.py",
            "verify_password_change.py",
            "verify_reply.py",
            "verify_wind_fix.py"
        ]
        cleanup_cmd = " && ".join([f"rm -f {project_dir}/{f}" for f in files_to_remove])
        client.exec_command(cleanup_cmd)

        # 2. SFTP Upload
        print("Uploading ALL modified files via SFTP...")
        sftp = client.open_sftp()
        try:
            for f in files_to_upload:
                local_path = f
                remote_path = f"{project_dir}/{f}"
                print(f"Uploading {local_path} to {remote_path}...")
                sftp.put(local_path, remote_path)
            print("All files uploaded successfully.")
        except Exception as e:
            print(f"SFTP Upload failed: {e}")
            return
        finally:
            sftp.close()

        # 3. Restart the main server
        print("Finding and killing existing uvicorn process...")
        stdin, stdout, stderr = client.exec_command("pgrep -f 'uvicorn main:app'")
        old_pids = stdout.read().decode().strip().split('\n')
        for pid in old_pids:
            if pid:
                print(f"Killing PID: {pid}")
                client.exec_command(f"kill -9 {pid}")
        
        time.sleep(2)
        
        print("Starting server in background...")
        # Start command using the established convention (new_venv and HTTPS)
        start_cmd = (
            f"cd {project_dir} && "
            f"nohup new_venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 "
            f"--ssl-keyfile key.pem --ssl-certfile cert.pem > server.log 2>&1 < /dev/null &"
        )
        client.exec_command(start_cmd)
        
        print("Server restart command issued. Waiting to verify...")
        time.sleep(5)
        
        stdin, stdout, stderr = client.exec_command("pgrep -f 'uvicorn main:app'")
        new_pids = stdout.read().decode().strip()
        if new_pids:
            print(f"Server successfully started. New PID(s): {new_pids}")
        else:
            print("WARNING: Server failed to start. Check server.log.")

    except Exception as e:
        print(f"Global deployment failed: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    deploy_full()
