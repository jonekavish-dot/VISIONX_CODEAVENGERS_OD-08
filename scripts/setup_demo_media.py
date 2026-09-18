"""
IVACS V-TRACE: Demo Scenario Media Generator
Creates deterministic, high-fidelity local demonstration media for the 4 hackathon scenarios:
1. normal_vehicle/      (Red Bus + TN01AB1234 -> Red Bus + TN01AB1234)
2. identity_mismatch/   (Red Bus + TN01AB1234 -> White Truck + TN01AB1234)
3. plate_swap/          (Red Bus + TN01AB1234 -> Red Bus + KA05CD5678)
4. unreadable_plate/    (Red Bus + TN01AB1234 -> Red Bus + Unreadable Plate)

Zero runtime internet dependencies. 100% deterministic and offline.
"""

import os
import cv2
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEMO_DIR = BASE_DIR / "data" / "demo"
SCENARIOS_DIR = DEMO_DIR / "scenarios"

def make_plate_image(plate_text: str, is_unreadable: bool = False) -> np.ndarray:
    """Renders a standard Indian HSRP license plate crop."""
    h, w = 60, 220
    if is_unreadable:
        img = np.full((h, w, 3), (120, 115, 110), dtype=np.uint8)
        # Add blur, mud splatter, and noise
        noise = np.random.normal(0, 25, (h, w, 3)).astype(np.uint8)
        img = cv2.add(img, noise)
        cv2.putText(img, "......", (40, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (70, 70, 70), 2)
        return cv2.GaussianBlur(img, (15, 15), 0)
        
    img = np.full((h, w, 3), (245, 245, 245), dtype=np.uint8)
    # Border
    cv2.rectangle(img, (0, 0), (w - 1, h - 1), (15, 15, 15), 2)
    # Blue IND strip
    cv2.rectangle(img, (2, 2), (28, h - 3), (180, 50, 20), -1)
    cv2.putText(img, "IND", (4, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
    # Plate Text
    cv2.putText(img, plate_text, (38, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.82, (15, 15, 15), 2, cv2.LINE_AA)
    return img

def make_different_vehicle_image() -> np.ndarray:
    """Synthesizes a realistic front-facing White/Silver Construction Tipper Truck."""
    vh, vw = 600, 500
    img = np.full((vh, vw, 3), (210, 215, 220), dtype=np.uint8)
    
    # Roof and Amber Beacon Lights
    cv2.rectangle(img, (120, 15), (170, 45), (30, 140, 255), -1)
    cv2.rectangle(img, (330, 15), (380, 45), (30, 140, 255), -1)
    
    # Windshield
    cv2.rectangle(img, (50, 60), (450, 240), (45, 55, 65), -1)
    cv2.rectangle(img, (48, 58), (452, 242), (30, 30, 30), 3)
    # Wipers
    cv2.line(img, (120, 235), (200, 150), (20, 20, 20), 4)
    cv2.line(img, (300, 235), (380, 150), (20, 20, 20), 4)
    
    # Heavy Front Grille
    cv2.rectangle(img, (90, 300), (410, 460), (35, 35, 38), -1)
    cv2.rectangle(img, (88, 298), (412, 462), (15, 15, 15), 3)
    for y in range(320, 450, 22):
        cv2.line(img, (110, y), (390, y), (170, 175, 180), 4)
        
    # Dual Headlights
    cv2.circle(img, (65, 340), 28, (240, 245, 210), -1)
    cv2.circle(img, (65, 340), 28, (60, 60, 60), 2)
    cv2.circle(img, (435, 340), 28, (240, 245, 210), -1)
    cv2.circle(img, (435, 340), 28, (60, 60, 60), 2)
    
    # Heavy Steel Bumper
    cv2.rectangle(img, (30, 475), (470, 565), (70, 72, 75), -1)
    cv2.rectangle(img, (28, 473), (472, 567), (30, 30, 30), 3)
    
    # Mounting bracket for license plate
    px1, py1, px2, py2 = 140, 490, 360, 550
    plate_patch = make_plate_image("TN01AB1234")
    plate_resized = cv2.resize(plate_patch, (px2 - px1, py2 - py1))
    img[py1:py2, px1:px2] = plate_resized
    
    return img

def setup_demo_scenarios():
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load base vehicle (Red Bus)
    sample_bus_path = DEMO_DIR / "sample_bus.jpg"
    if not sample_bus_path.exists():
        sample_bus_path = DEMO_DIR / "bus_with_plate.jpg"
        
    bus_full = cv2.imread(str(sample_bus_path))
    if bus_full is None:
        raise RuntimeError(f"Base demo vehicle not found at {sample_bus_path}")
        
    # Crop bus vehicle body
    bh, bw = bus_full.shape[:2]
    bus_crop1 = bus_full[int(bh * 0.18):int(bh * 0.90), int(bw * 0.08):int(bw * 0.92)].copy()
    
    # Second crop with minor illumination variation
    bus_crop2 = cv2.convertScaleAbs(bus_crop1, alpha=1.03, beta=3)
    
    # Synthesize different vehicle (White construction truck)
    diff_truck = make_different_vehicle_image()
    
    # Plates
    plate_tn = make_plate_image("TN01AB1234")
    plate_ka = make_plate_image("KA05CD5678")
    plate_unreadable = make_plate_image("", is_unreadable=True)
    
    # Scenarios Definitions
    scenarios_data = {
        "normal_vehicle": {
            "step1_vehicle": bus_crop1,
            "step1_plate": plate_tn,
            "step2_vehicle": bus_crop2,
            "step2_plate": plate_tn,
        },
        "identity_mismatch": {
            "step1_vehicle": bus_crop1,
            "step1_plate": plate_tn,
            "step2_vehicle": diff_truck,
            "step2_plate": plate_tn,
        },
        "plate_swap": {
            "step1_vehicle": bus_crop1,
            "step1_plate": plate_tn,
            "step2_vehicle": bus_crop2,
            "step2_plate": plate_ka,
        },
        "unreadable_plate": {
            "step1_vehicle": bus_crop1,
            "step1_plate": plate_tn,
            "step2_vehicle": bus_crop2,
            "step2_plate": plate_unreadable,
        }
    }
    
    for s_name, data in scenarios_data.items():
        s_dir = SCENARIOS_DIR / s_name
        s_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(s_dir / "step1_historical_vehicle.jpg"), data["step1_vehicle"])
        cv2.imwrite(str(s_dir / "step1_historical_plate.jpg"), data["step1_plate"])
        cv2.imwrite(str(s_dir / "step2_current_vehicle.jpg"), data["step2_vehicle"])
        cv2.imwrite(str(s_dir / "step2_current_plate.jpg"), data["step2_plate"])
        print(f"Created demo scenario media: {s_dir}")

if __name__ == "__main__":
    setup_demo_scenarios()
