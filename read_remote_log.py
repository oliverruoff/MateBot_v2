import paramiko
import sys

def run_commands():
    hostname = 'matebot.local'
    username = 'matebot'
    password = '' # ask user for it!
    
    # Check the last 500 lines but skip the CRC mismatches to see what else is there
    commands = [
        "grep -v \"CRC mismatch\" develop/MateBot_v2/app_output.log | tail -n 50"
    ]

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname, username=username, password=password)
        
        for cmd in commands:
            print(f"--- Running: {cmd} ---")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            out = stdout.read().decode()
            if out: print(out)
            else: print("No non-CRC-mismatch lines found in the last part of the log.")
            print("\n")
            
        ssh.close()
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    run_commands()
