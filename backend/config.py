"""
IVACS V-TRACE Configuration
Centralized configuration for camera zones, video inputs, sampling, and paths.
"""

import os
from pathlib import Path
from pydantic import BaseModel
from typing import Dict

BASE_DIR = Path(__file__).resolve().parent.parent

# Directories
DATA_DIR = BASE_DIR / "data"
DEMO_DIR = DATA_DIR / "demo"
EVIDENCE_DIR = DATA_DIR / "evidence"
SCENARIOS_DIR = DEMO_DIR / "scenarios"
DB_PATH = BASE_DIR / "vtrace.db"

# Ensure runtime directories exist
DEMO_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)

# Default Demo Video Path
DEFAULT_DEMO_VIDEO = str(DEMO_DIR / "construction_site.mp4")

# Frame Sampling configuration (Process every N frames to ensure fast laptop inference)
PROCESS_EVERY_N_FRAMES = int(os.getenv("PROCESS_EVERY_N_FRAMES", "3"))

# Temporal Deduplication Cooldown (Seconds to suppress duplicate identity alert spam)
IDENTITY_EVENT_COOLDOWN_SECONDS = int(os.getenv("IDENTITY_EVENT_COOLDOWN_SECONDS", "5"))

# Vehicle Detection Confidence Threshold
VEHICLE_CONF_THRESHOLD = float(os.getenv("VEHICLE_CONF_THRESHOLD", "0.40"))
PLATE_CONF_THRESHOLD = float(os.getenv("PLATE_CONF_THRESHOLD", "0.30"))
OCR_CONF_THRESHOLD = float(os.getenv("OCR_CONF_THRESHOLD", "0.30"))

# Vehicle Visual Fingerprint Engine (Demo Calibration Thresholds)
# NOTE: These are empirical demo calibration thresholds, not claimed accuracy figures.
IDENTITY_HIGH_THRESHOLD = float(os.getenv("IDENTITY_HIGH_THRESHOLD", "0.85"))
IDENTITY_LOW_THRESHOLD = float(os.getenv("IDENTITY_LOW_THRESHOLD", "0.60"))

# Target Vehicle Classes (COCO indices: 2=car, 3=motorcycle, 5=bus, 7=truck)
TARGET_VEHICLE_CLASSES = ["car", "truck", "bus", "motorcycle"]

class CameraConfig(BaseModel):
    id: str
    name: str
    zone: str
    default_source: str = ""

CAMERAS: Dict[str, CameraConfig] = {
    "CAM-01": CameraConfig(
        id="CAM-01",
        name="Gate Entrance",
        zone="GATE_IN",
        default_source=DEFAULT_DEMO_VIDEO
    ),
    "CAM-02": CameraConfig(
        id="CAM-02",
        name="Material Yard",
        zone="MATERIAL_YARD",
        default_source=""
    ),
    "CAM-03": CameraConfig(
        id="CAM-03",
        name="Active Zone",
        zone="ACTIVE_ZONE",
        default_source=""
    ),
    "CAM-04": CameraConfig(
        id="CAM-04",
        name="Exit",
        zone="GATE_OUT",
        default_source=""
    ),
}

DEFAULT_CAMERA_ID = "CAM-01"
