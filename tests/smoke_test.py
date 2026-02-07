import subprocess
import time
import requests
import os

def test_startup():
    print("Starting MateBot v2 Smoke Test...")
    # Set simulation mode
    env = os.environ.copy()
    env["MATEBOT_SIM"] = "1"
    
    # Start the main script in the background
    process = subprocess.Popen(["python3", "main.py"], env=env)
    
    # Wait for server to start
    max_retries = 10
    started = False
    for i in range(max_retries):
        try:
            res = requests.get("http://localhost:8000/", timeout=1)
            if res.status_code == 200:
                print("Web Server is UP!")
                started = True
                break
        except:
            pass
        print(f"Waiting for server... ({i+1}/{max_retries})")
        time.sleep(2)
    
    if started:
        # Check API
        try:
            res = requests.get("http://localhost:8000/api/poi")
            if res.status_code == 200:
                print("API is functional!")
        except Exception as e:
            print(f"API Check failed: {e}")
            started = False

    # Cleanup
    print("Shutting down...")
    process.terminate()
    process.wait()
    
    if started:
        print("Smoke Test PASSED")
    else:
        print("Smoke Test FAILED")
        exit(1)

if __name__ == "__main__":
    test_startup()
