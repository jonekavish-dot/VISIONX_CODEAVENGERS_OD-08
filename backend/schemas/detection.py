"""
IVACS V-TRACE Pydantic Schemas
Defines structured detection events, status codes, and API response models.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from enum import Enum
from datetime import datetime

class ProcessingStatus(str, Enum):
    DETECTED = "DETECTED"
    NO_VEHICLE = "NO_VEHICLE"
    NO_PLATE = "NO_PLATE"
    PLATE_UNREADABLE = "PLATE_UNREADABLE"
    ERROR = "ERROR"

class DetectionEvent(BaseModel):
    id: Optional[int] = None
    camera_id: str = "CAM-01"
    zone: str = "GATE_IN"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    frame_number: int = 0
    status: ProcessingStatus = ProcessingStatus.DETECTED
    vehicle_class: Optional[str] = None
    vehicle_confidence: Optional[float] = None
    vehicle_bbox: Optional[List[int]] = None  # [x1, y1, x2, y2]
    plate: Optional[str] = None               # normalized plate text
    raw_plate: Optional[str] = None           # raw uncorrected OCR text
    plate_confidence: Optional[float] = None   # detector confidence for plate bbox
    ocr_confidence: Optional[float] = None     # EasyOCR confidence
    plate_bbox: Optional[List[int]] = None    # [x1, y1, x2, y2]
    vehicle_crop_path: Optional[str] = None
    plate_crop_path: Optional[str] = None
    frame_path: Optional[str] = None
    annotated_frame_path: Optional[str] = None
    # Vehicle Identity Extension Fields
    vehicle_id: Optional[str] = None
    visual_similarity: Optional[float] = None
    identity_event: Optional[str] = None
    identity_match_status: Optional[str] = None
    created_at: Optional[str] = Field(default_factory=lambda: datetime.now().isoformat())

class DetectionListResponse(BaseModel):
    total: int
    detections: List[DetectionEvent]

class DemoStatusResponse(BaseModel):
    is_running: bool
    camera_id: str
    video_source: str
    current_frame: int
    total_frames: int
    processed_count: int
    detections_count: int
    fps: float
    message: str

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    runtime_device: str
    models_loaded: bool
