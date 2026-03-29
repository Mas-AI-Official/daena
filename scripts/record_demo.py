"""
Daena Demo Recording Script
Captures the screen while Playwright automates a 60-second product walkthrough.
Uses mss for screen capture and cv2 for video encoding.

Usage:
    1. Start backend:  start-backend.bat
    2. Start frontend: cd frontend && npm run dev
    3. Run:  python scripts/record_demo.py

Output: Doc/demo/daena-demo-raw.mp4
"""
import os
import subprocess
import sys
import threading
import time
import urllib.request

import cv2
import numpy as np
import mss

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "Doc", "demo")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "daena-demo-raw.mp4")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
AUTOMATION_SCRIPT = os.path.join(PROJECT_ROOT, "frontend", "demo-automation.mjs")

# Recording settings
WIDTH = 1920
HEIGHT = 1080
FPS = 15
MAX_DURATION = 80  # hard cap in seconds


class ScreenRecorder:
    """Captures the primary monitor and writes to mp4 in real time."""

    def __init__(self, output_path: str, width: int, height: int, fps: int):
        self.output_path = output_path
        self.width = width
        self.height = height
        self.fps = fps
        self.recording = False
        self.frame_count = 0
        self._thread = None

    def start(self):
        self.recording = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print(f"[recorder] Capturing {self.width}x{self.height} @ {self.fps}fps")

    def stop(self):
        self.recording = False
        if self._thread:
            self._thread.join(timeout=10)
        duration = self.frame_count / self.fps if self.fps else 0
        print(f"[recorder] Done: {self.frame_count} frames ({duration:.1f}s)")

    def _capture_loop(self):
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(
            self.output_path, fourcc, self.fps, (self.width, self.height)
        )

        with mss.mss() as sct:
            monitor = sct.monitors[1]  # primary monitor
            interval = 1.0 / self.fps
            t_start = time.time()

            while self.recording and (time.time() - t_start) < MAX_DURATION:
                t0 = time.time()

                img = np.array(sct.grab(monitor))
                frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

                if frame.shape[1] != self.width or frame.shape[0] != self.height:
                    frame = cv2.resize(frame, (self.width, self.height))

                writer.write(frame)
                self.frame_count += 1

                elapsed = time.time() - t0
                if elapsed < interval:
                    time.sleep(interval - elapsed)

        writer.release()


def preflight():
    """Verify backend and frontend are running."""
    ok = True

    # Backend health
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:8000/api/v1/health", timeout=10)
        if resp.status == 200:
            print("[preflight] Backend:  OK")
        else:
            print(f"[preflight] Backend:  HTTP {resp.status}")
            ok = False
    except Exception as e:
        print(f"[preflight] Backend:  NOT RUNNING ({e})")
        ok = False

    # Frontend (Vite may bind to IPv6, try both)
    frontend_ok = False
    for addr in ["http://127.0.0.1:5173", "http://localhost:5173", "http://[::1]:5173"]:
        try:
            resp = urllib.request.urlopen(addr, timeout=5)
            if resp.status == 200:
                print(f"[preflight] Frontend: OK ({addr})")
                frontend_ok = True
                break
        except Exception:
            continue
    if not frontend_ok:
        print("[preflight] Frontend: NOT RUNNING")
        ok = False

    if not ok:
        print("\nStart both servers before recording:")
        print("  Terminal 1: start-backend.bat")
        print("  Terminal 2: cd frontend && npm run dev")
        sys.exit(1)

    # Automation script exists
    if not os.path.exists(AUTOMATION_SCRIPT):
        print(f"[preflight] Missing: {AUTOMATION_SCRIPT}")
        sys.exit(1)

    print("[preflight] All checks passed.\n")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    preflight()

    recorder = ScreenRecorder(OUTPUT_PATH, WIDTH, HEIGHT, FPS)

    print("[demo] Starting screen recorder...")
    recorder.start()
    time.sleep(1)  # warm up

    print("[demo] Launching browser automation...")
    try:
        result = subprocess.run(
            ["node", AUTOMATION_SCRIPT],
            cwd=FRONTEND_DIR,
            timeout=MAX_DURATION,
            capture_output=False,
        )
        if result.returncode != 0:
            print(f"[demo] Automation exited with code {result.returncode}")
    except subprocess.TimeoutExpired:
        print("[demo] Automation timed out.")
    except FileNotFoundError:
        print("[demo] ERROR: 'node' not found. Is Node.js installed?")
    finally:
        time.sleep(2)  # capture final frames
        recorder.stop()

    # Report
    if os.path.exists(OUTPUT_PATH):
        size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
        duration = recorder.frame_count / FPS
        print(f"\n{'=' * 50}")
        print(f"Recording saved: {OUTPUT_PATH}")
        print(f"Size: {size_mb:.1f} MB | Frames: {recorder.frame_count} | Duration: {duration:.1f}s")
        print(f"{'=' * 50}")
        print(f"\nNext: python scripts/add_title_card.py")
    else:
        print("[demo] ERROR: No output file created.")
        sys.exit(1)


if __name__ == "__main__":
    main()
