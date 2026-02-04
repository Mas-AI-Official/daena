import subprocess
import sys
import os
import time
import signal

def signal_handler(sig, frame):
    print("\nStopping DaenaBot Hands Service...")
    sys.exit(0)

def main():
    # Assume running from project root
    script_path = os.path.join("backend", "services", "daenabot_hands_server.py")
    
    # If running from scripts dir, adjust path
    if not os.path.exists(script_path) and os.path.exists(os.path.join("..", script_path)):
        os.chdir("..")
        
    if not os.path.exists(script_path):
        # absolute check
        local_check = os.path.join(os.path.dirname(__file__), "..", "backend", "services", "daenabot_hands_server.py")
        if os.path.exists(local_check):
             script_path = local_check
             # Change to root
             os.chdir(os.path.join(os.path.dirname(__file__), ".."))
        else:
            print(f"Error: {script_path} not found!")
            return

    print(f"Starting DaenaBot Hands Service from {os.getcwd()}...")
    
    # Environment Setup
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    
    cmd = [sys.executable, script_path]
    
    try:
        # Run safely
        process = subprocess.Popen(cmd, env=env)
        print(f"DaenaBot Hands started with PID: {process.pid}")
        
        # Keep alive monitor
        while True:
            ret = process.poll()
            if ret is not None:
                print(f"Service exited with code {ret}")
                break
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("Stopping service...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    main()
