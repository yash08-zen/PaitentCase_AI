"""
scripts/generate_handwritten_eval_dataset.py
--------------------------------------------
Generates synthetic and realistic test prescription images for the evaluation benchmark:
  1. rx_eval_01_printed_reference.png (Clean printed reference)
  2. rx_eval_02_cursive_mild.png (Mild cursive doctor handwriting)
  3. rx_eval_03_slanted_handwritten.png (Faint slanted cursive handwriting)
  4. rx_eval_04_bilingual_printed.png (Bilingual Devanagari / English prescription)
  5. rx_eval_05_cursive_scrawl.png (Degraded doctor cursive scrawl)
"""

import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

EVAL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "eval_data", "handwritten")
os.makedirs(EVAL_DIR, exist_ok=True)


def create_base_canvas(width=800, height=500, bg_color=(255, 255, 255)):
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    # Subtle clinic header line
    draw.line([(40, 70), (width - 40, 70)], fill=(180, 180, 180), width=1)
    return img, draw


def generate_printed_sample():
    """Generates clean printed prescription."""
    img, draw = create_base_canvas()
    font = ImageFont.load_default()

    draw.text((50, 30), "CITY CLINIC HEALTHCARE - OUTPATIENT RECORD", fill=(20, 20, 20), font=font)
    draw.text((50, 90), "Patient: Rajesh Kumar  |  Age: 45  |  Date: 2026-10-24", fill=(50, 50, 50), font=font)
    draw.text((50, 130), "Rx:", fill=(10, 10, 10), font=font)
    draw.text((70, 170), "1. Amoxicillin 500mg capsules TID x 7 days", fill=(20, 20, 20), font=font)
    draw.text((70, 210), "2. Paracetamol 650mg tablets SOS x 3 days", fill=(20, 20, 20), font=font)
    draw.text((50, 320), "Doctor: Dr. R. Sharma, MD (Reg #MED-48210)", fill=(40, 40, 40), font=font)

    out_path = os.path.join(EVAL_DIR, "rx_eval_01_printed_reference.png")
    img.save(out_path)
    print(f"Generated {out_path}")


def generate_cursive_sample():
    """Generates cursive doctor handwriting style with slight offsets and stroke jitter."""
    img, draw = create_base_canvas(bg_color=(250, 250, 245))
    font = ImageFont.load_default()

    draw.text((50, 30), "City Clinic Outpatient", fill=(40, 40, 60), font=font)
    draw.text((50, 100), "Rx:", fill=(30, 30, 80), font=font)

    # Simulated connected handwritten script
    text_lines = [
        "Metformin 500mg BD",
        "Glimepiride 1mg OD",
        "Dr. S. Kulkarni",
    ]

    y_pos = 150
    for line in text_lines:
        x_pos = 70
        for ch in line:
            # Add small random pen jitter
            dy = random.randint(-1, 1)
            draw.text((x_pos, y_pos + dy), ch, fill=(35, 45, 110), font=font)
            x_pos += 8 + random.randint(0, 2)
        y_pos += 45

    # Apply light blur to simulate ballpoint ink bleeding
    img = img.filter(ImageFilter.GaussianBlur(radius=0.4))
    out_path = os.path.join(EVAL_DIR, "rx_eval_02_cursive_mild.png")
    img.save(out_path)
    print(f"Generated {out_path}")


def generate_slanted_handwritten_sample():
    """Generates slanted cursive doctor handwriting."""
    img, draw = create_base_canvas(bg_color=(253, 252, 248))
    font = ImageFont.load_default()

    draw.text((50, 30), "Care Hospital Rx", fill=(80, 80, 80), font=font)
    draw.text((50, 110), "Rx:", fill=(50, 50, 90), font=font)

    text_lines = [
        "Atorvastatin 20mg HS",
        "Aspirin 75mg OD",
        "Dr. P. Joshi",
    ]

    y_pos = 160
    for line in text_lines:
        x_pos = 80
        for i, ch in enumerate(line):
            # Slanted displacement
            slant_dx = int(i * 0.4)
            draw.text((x_pos + slant_dx, y_pos), ch, fill=(60, 60, 100), font=font)
            x_pos += 8
        y_pos += 40

    out_path = os.path.join(EVAL_DIR, "rx_eval_03_slanted_handwritten.png")
    img.save(out_path)
    print(f"Generated {out_path}")


def generate_bilingual_sample():
    """Generates bilingual printed prescription."""
    img, draw = create_base_canvas()
    font = ImageFont.load_default()

    draw.text((50, 30), "आरोग्य केंद्र / Health Center", fill=(20, 20, 20), font=font)
    draw.text((50, 110), "Rx:", fill=(10, 10, 10), font=font)
    draw.text((70, 160), "Paracetamol 500mg / पैरासिटामोल 500mg BD", fill=(20, 20, 20), font=font)
    draw.text((70, 210), "Cetirizine 10mg / सेटिरिज़िन 10mg OD", fill=(20, 20, 20), font=font)

    out_path = os.path.join(EVAL_DIR, "rx_eval_04_bilingual_printed.png")
    img.save(out_path)
    print(f"Generated {out_path}")


def generate_cursive_scrawl_sample():
    """Generates low-contrast degraded doctor cursive scrawl."""
    img, draw = create_base_canvas(bg_color=(245, 245, 240))
    font = ImageFont.load_default()

    draw.text((50, 40), "Clinic Rx:", fill=(120, 120, 120), font=font)

    # Scrawl lines with low contrast
    draw.text((80, 150), "Azithro 500 OD x 3d", fill=(140, 130, 150), font=font)
    draw.text((80, 210), "Panto 40 OD", fill=(140, 130, 150), font=font)

    # Add noise lines simulating paper folds and pen scribbles
    draw.line([(60, 180), (300, 175)], fill=(200, 200, 200), width=1)
    draw.line([(70, 240), (280, 235)], fill=(210, 210, 210), width=1)

    img = img.filter(ImageFilter.GaussianBlur(radius=0.7))
    out_path = os.path.join(EVAL_DIR, "rx_eval_05_cursive_scrawl.png")
    img.save(out_path)
    print(f"Generated {out_path}")


def main():
    generate_printed_sample()
    generate_cursive_sample()
    generate_slanted_handwritten_sample()
    generate_bilingual_sample()
    generate_cursive_scrawl_sample()
    print("All 5 evaluation images generated in", EVAL_DIR)


if __name__ == "__main__":
    main()
