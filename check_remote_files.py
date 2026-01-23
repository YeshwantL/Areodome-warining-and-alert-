import paramiko

HOSTNAME = "121.240.10.8"
USERNAME = "mwomumbai"
PASSWORD = "mwomumbai@4321"

def check_files():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOSTNAME, username=USERNAME, password=PASSWORD)
        stdin, stdout, stderr = client.exec_command("tail -n 100 ./app/server.log")
        print(stdout.read().decode())
        print(stderr.read().decode())
    finally:
        client.close()

if __name__ == "__main__":
    check_files()
