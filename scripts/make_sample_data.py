"""Generate sample test documents (text, PDF, PNG) in data/uploads for verification.

Run: uv run python scripts/make_sample_data.py
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path("data/uploads")
OUT.mkdir(parents=True, exist_ok=True)

# --- 1. text file ------------------------------------------------------------
text = """# Northwind Robotics — Q3 2026 Financial Report

## Executive summary
Revenue for Q3 2026 grew 12% year over year to 4.2 million dollars, driven by
strong demand for the Atlas robotic arm. Gross margin improved to 61% from 58%
in the same quarter last year, reflecting lower component costs.

## Highlights
- Revenue: $4.2M (up 12% YoY)
- Gross margin: 61% (up 3 points YoY)
- New Berlin office opened September 3, 2026, adding 40 employees
- Atlas robotic arm shipped 310 units, up from 240 units in Q3 2025
- Operating expenses were $2.9 million, up 8% year over year

## Risks
Component supply constraints could delay Q4 deliveries. The company expects
Q4 revenue between $4.6 million and $4.8 million.
"""
(OUT / "northwind_q3_report.md").write_text(text)

(OUT / "meeting_notes.txt").write_text(
    """Standup notes - October 14

Priya reported that the Berlin office lease is signed and networking is done.
Marcus is blocked on the Atlas firmware release; the vendor promised a patch by
Friday. We agreed to demo the robotic arm at the robotics expo in November.

Lunch logistics: we ordered 12 pizzas for the team retro.
"""
)

# --- 2. PDF -------------------------------------------------------------------
from reportlab.lib.pagesizes import LETTER  # type: ignore
from reportlab.pdfgen import canvas  # type: ignore

pdf_path = OUT / "atlas_datasheet.pdf"
c = canvas.Canvas(str(pdf_path), pagesize=LETTER)
c.setFont("Helvetica-Bold", 18)
c.drawString(72, 720, "Atlas Robotic Arm — Datasheet")
c.setFont("Helvetica", 11)
lines = [
    "Payload: 7.5 kg at full reach",
    "Repeatability: +/- 0.02 mm",
    "Reach: 1,250 mm",
    "Weight: 23 kg",
    "Repeatable trajectory accuracy under 0.05 mm",
    "Controller: proprietary AtlasOS 4.2",
    "Price: $28,400 per unit",
]
y = 680
for ln in lines:
    c.drawString(72, y, ln)
    y -= 22
c.drawString(72, y - 20, "Availability: 310 units shipped in Q3 2026")
c.showPage()
c.setFont("Helvetica-Bold", 14)
c.drawString(72, 720, "Safety and Compliance")
c.setFont("Helvetica", 11)
y = 680
for ln in ["ISO 10218 certified", "CE and UL listed",
           "Emergency stop within 120 milliseconds", "Operating temperature 5C to 45C"]:
    c.drawString(72, y, ln)
    y -= 22
c.showPage()
c.save()

# --- 3. image ----------------------------------------------------------------
img = Image.new("RGB", (640, 420), (18, 22, 34))
d = ImageDraw.Draw(img)
d.rectangle([40, 40, 600, 200], outline=(110, 168, 254), width=5)
d.text((60, 100), "ATLAS ROBOTIC ARM", fill=(230, 232, 238))
d.rectangle([60, 250, 250, 360], fill=(67, 217, 173))
d.text((75, 295), "REACH 1250mm", fill=(10, 20, 25))
d.rectangle([280, 250, 470, 360], fill=(227, 179, 65))
d.text((300, 295), "PAYLOAD 7.5kg", fill=(10, 20, 25))
d.text((60, 385), "Northwind Robotics - Atlas v4", fill=(160, 168, 180))
img.save(OUT / "atlas_arm.png")

print("created:")
for p in sorted(OUT.iterdir()):
    print(f"  {p} ({p.stat().st_size} bytes)")
