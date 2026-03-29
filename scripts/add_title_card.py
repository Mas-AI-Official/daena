"""
Add Title Card Overlay to Daena Demo Video
Prepends a 3-second title card with fade in/out:
"Daena: Governed Multi-Agent AI Platform | MAS-AI Technologies"

Usage:  python scripts/add_title_card.py
Input:  Doc/demo/daena-demo-raw.mp4
Output: Doc/demo/daena-demo.mp4
"""
import os
import sys

import cv2
import numpy as np

INPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "Doc", "demo", "daena-demo-raw.mp4",
)
OUTPUT_PATH = INPUT_PATH.replace("-raw.mp4", ".mp4")
TITLE_DURATION = 3  # seconds


def create_title_frame(width: int, height: int) -> np.ndarray:
    """Dark gradient background with centered title text."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)

    # Gradient: dark navy to near-black
    for y in range(height):
        ratio = y / height
        frame[y, :] = [int(40 * (1 - ratio)), int(20 * (1 - ratio)), int(8 * (1 - ratio))]

    font = cv2.FONT_HERSHEY_SIMPLEX
    cx = width // 2

    # "Daena" (large, white with cyan glow)
    title = "Daena"
    t_scale, t_thick = 3.0, 4
    t_size = cv2.getTextSize(title, font, t_scale, t_thick)[0]
    t_x = cx - t_size[0] // 2
    t_y = height // 2 - 50
    # Glow layer (cyan)
    cv2.putText(frame, title, (t_x, t_y), font, t_scale, (255, 212, 0), t_thick + 3, cv2.LINE_AA)
    # Main text (white)
    cv2.putText(frame, title, (t_x, t_y), font, t_scale, (255, 255, 255), t_thick, cv2.LINE_AA)

    # Subtitle
    sub = "Governed Multi-Agent AI Platform"
    s_scale, s_thick = 1.0, 2
    s_size = cv2.getTextSize(sub, font, s_scale, s_thick)[0]
    s_x = cx - s_size[0] // 2
    s_y = t_y + 70
    cv2.putText(frame, sub, (s_x, s_y), font, s_scale, (200, 200, 200), s_thick, cv2.LINE_AA)

    # Company name (cyan accent)
    comp = "MAS-AI Technologies Inc."
    c_scale, c_thick = 0.7, 1
    c_size = cv2.getTextSize(comp, font, c_scale, c_thick)[0]
    c_x = cx - c_size[0] // 2
    c_y = s_y + 55
    cv2.putText(frame, comp, (c_x, c_y), font, c_scale, (0, 200, 255), c_thick, cv2.LINE_AA)

    return frame


def main():
    if not os.path.exists(INPUT_PATH):
        print(f"ERROR: Input not found: {INPUT_PATH}")
        print("Run record_demo.py first.")
        sys.exit(1)

    cap = cv2.VideoCapture(INPUT_PATH)
    fps = cap.get(cv2.CAP_PROP_FPS) or 15
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Input: {width}x{height} @ {fps:.0f}fps, {total_frames} frames")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(OUTPUT_PATH, fourcc, fps, (width, height))

    # Generate title card
    title_frame = create_title_frame(width, height)
    n_title = int(fps * TITLE_DURATION)
    fade_frames = int(fps * 0.5)

    print(f"Writing {TITLE_DURATION}s title card ({n_title} frames)...")
    for i in range(n_title):
        if i < fade_frames:
            alpha = i / fade_frames
        elif i > n_title - fade_frames:
            alpha = (n_title - i) / fade_frames
        else:
            alpha = 1.0
        writer.write((title_frame * alpha).astype(np.uint8))

    # Append original video
    print(f"Appending {total_frames} demo frames...")
    count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        writer.write(frame)
        count += 1

    cap.release()
    writer.release()

    total = n_title + count
    duration = total / fps
    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)

    print(f"\nOutput: {OUTPUT_PATH}")
    print(f"Duration: {duration:.1f}s ({TITLE_DURATION}s title + {count / fps:.1f}s demo)")
    print(f"Frames: {total} | Size: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
