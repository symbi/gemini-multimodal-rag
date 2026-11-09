"""Generate short sample video + audio for verification (uses ffmpeg).

Run: uv run python scripts/make_media_sample.py
"""
from __future__ import annotations

import subprocess
from pathlib import Path

OUT = Path("data/uploads")
OUT.mkdir(parents=True, exist_ok=True)

# --- video: 8 seconds, 640x360, with a visible title -----------------------
video = OUT / "atlas_demo_clip.mp4"
subprocess.run(
    ["ffmpeg", "-y", "-f", "lavfi", "-i",
     "color=c=0x12161F:s=640x360:d=8",
     "-vf", "drawtext=text='ATLAS ROBOTIC ARM DEMO':fontcolor=white:fontsize=34:x=(w-text_w)/2:y=120,"
            "drawtext=text='Reach 1250mm - Payload 7.5kg':fontcolor=0x6EA8FE:fontsize=24:x=(w-text_w)/2:y=200",
     "-r", "24", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
    check=True, capture_output=True,
)

# --- audio: 10 seconds, spoken-ish tone ------------------------------------
audio = OUT / "factory_ambience.wav"
subprocess.run(
    ["ffmpeg", "-y", "-f", "lavfi", "-i",
     "sine=frequency=220:duration=10", "-ac", "1", "-ar", "44100", str(audio)],
    check=True, capture_output=True,
)

# --- oversize video (to test the 120s limit) -------------------------------
long_video = OUT / "too_long_clip.mp4"
subprocess.run(
    ["ffmpeg", "-y", "-f", "lavfi", "-i",
     "color=c=0x12161F:s=320x180:d=130", "-r", "12", "-c:v", "libx264",
     "-pix_fmt", "yuv420p", str(long_video)],
    check=True, capture_output=True,
)

for p in (video, audio, long_video):
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
        capture_output=True, text=True,
    ).stdout.strip()
    print(f"created {p} ({p.stat().st_size} bytes, {float(dur):.1f}s)")
