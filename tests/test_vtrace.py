"""
IVACS V-TRACE Automated Test Suite
Verifies all 7 critical areas required by the hackathon specification:
1. Video source initialization
2. Invalid video handling
3. Frame processing with no detection
4. OCR empty result & safe handling
5. Valid structured DetectionEvent
6. Database insertion and retrieval
7. Evidence image creation
"""

import os
import pytest
import numpy as np
import cv2
from pathlib import Path

from backend.config import DEFAULT_DEMO_VIDEO, EVIDENCE_DIR, DB_PATH
from backend.video.base_source import VideoSource
from backend.video.mp4_source import MP4Source
from backend.video.rtsp_source import RTSPSource
from backend.video.webcam_source import WebcamSource
from backend.schemas.detection import DetectionEvent, ProcessingStatus
from backend.database.database import (
    init_db,
    insert_detection,
    get_latest_detection,
    get_all_detections,
    get_total_detections_count
)
from backend.ocr.plate_ocr import PlateOCR
from backend.detection.vehicle_detector import VehicleDetector
from backend.detection.plate_detector import PlateDetector
from backend.services.frame_processor import FrameProcessor

# 1. Test Video Source Initialization
def test_video_source_initialization():
    assert os.path.exists(DEFAULT_DEMO_VIDEO), f"Demo video should exist at {DEFAULT_DEMO_VIDEO}"
    source = MP4Source(DEFAULT_DEMO_VIDEO, camera_id="CAM-01")
    opened = source.open()
    assert opened is True
    assert source.is_opened is True
    assert source.get_total_frames() > 0
    assert source.get_fps() > 0
    
    success, frame, f_num = source.read_frame()
    assert success is True
    assert frame is not None
    assert f_num == 1
    assert frame.shape[0] > 0 and frame.shape[1] > 0
    source.close()
    assert source.is_opened is False

    # Also test RTSP and Webcam object instantiation
    rtsp = RTSPSource("rtsp://mock-camera:554/live")
    assert rtsp.source_uri == "rtsp://mock-camera:554/live"
    webcam = WebcamSource(0)
    assert webcam.device_index == 0

# 2. Test Invalid Video Handling
def test_invalid_video_handling():
    invalid_path = "data/demo/non_existent_file_xyz.mp4"
    source = MP4Source(invalid_path, camera_id="CAM-01")
    opened = source.open()
    assert opened is False
    assert source.is_opened is False
    
    # Reading from unopened/invalid source should never crash
    success, frame, f_num = source.read_frame()
    assert success is False
    assert frame is None
    source.close()

# 3. Test Frame Processing with No Detection
def test_frame_processing_with_no_detection():
    processor = FrameProcessor()
    # Create blank solid gray frame with zero vehicles
    blank_frame = np.full((720, 1280, 3), 128, dtype=np.uint8)
    
    events, annotated = processor.process_frame(
        frame=blank_frame,
        frame_number=1,
        camera_id="CAM-01",
        save_evidence=False
    )
    
    assert len(events) >= 1
    event = events[0]
    assert event.status == ProcessingStatus.NO_VEHICLE
    assert event.vehicle_class is None
    assert event.plate is None
    assert annotated is not None
    assert annotated.shape == blank_frame.shape

# 4. Test OCR Empty Result & Safe Handling
def test_ocr_empty_result():
    ocr = PlateOCR()
    # Blank white patch with no text
    empty_crop = np.full((60, 200, 3), 255, dtype=np.uint8)
    result = ocr.recognize(empty_crop)
    
    assert "raw_text" in result
    assert "normalized_text" in result
    assert "ocr_confidence" in result
    assert result["raw_text"] == ""
    assert result["normalized_text"] is None
    assert result["ocr_confidence"] == 0.0

    # Test random uniform noise - should NOT hallucinate a plate
    noise_crop = np.random.randint(0, 256, (60, 200, 3), dtype=np.uint8)
    noise_res = ocr.recognize(noise_crop)
    assert noise_res["normalized_text"] is None

# 5. Test Valid Structured DetectionEvent
def test_valid_structured_detection_event():
    event = DetectionEvent(
        camera_id="CAM-01",
        zone="GATE_IN",
        timestamp="2026-09-18T10:30:00",
        frame_number=120,
        status=ProcessingStatus.DETECTED,
        vehicle_class="truck",
        vehicle_confidence=0.91,
        plate="TN01AB1234",
        raw_plate="TN 01 AB 1234",
        plate_confidence=0.88,
        ocr_confidence=0.93,
        vehicle_bbox=[100, 200, 500, 600],
        plate_bbox=[250, 480, 420, 520]
    )
    
    data = event.model_dump()
    assert data["camera_id"] == "CAM-01"
    assert data["zone"] == "GATE_IN"
    assert data["vehicle_class"] == "truck"
    assert data["vehicle_confidence"] == 0.91
    assert data["plate"] == "TN01AB1234"
    assert data["plate_confidence"] == 0.88
    assert data["ocr_confidence"] == 0.93
    assert data["vehicle_bbox"] == [100, 200, 500, 600]
    assert data["plate_bbox"] == [250, 480, 420, 520]

# 6. Test Database Insertion
def test_database_insertion():
    init_db()
    initial_count = get_total_detections_count()
    
    test_event = DetectionEvent(
        camera_id="CAM-01",
        zone="GATE_IN",
        timestamp="2026-09-18T10:30:00",
        frame_number=999,
        status=ProcessingStatus.DETECTED,
        vehicle_class="car",
        vehicle_confidence=0.89,
        plate="KA05MH2024",
        raw_plate="KA05MH2024",
        plate_confidence=0.85,
        ocr_confidence=0.92,
        vehicle_bbox=[50, 100, 300, 400],
        plate_bbox=[120, 320, 230, 360],
        vehicle_crop_path="data/evidence/test_veh.jpg",
        plate_crop_path="data/evidence/test_plate.jpg",
        frame_path="data/evidence/test_frame.jpg"
    )
    
    inserted_id = insert_detection(test_event)
    assert inserted_id is not None
    assert inserted_id > 0
    
    new_count = get_total_detections_count()
    assert new_count == initial_count + 1
    
    latest = get_latest_detection()
    assert latest is not None
    assert latest.plate == "KA05MH2024"
    assert latest.vehicle_class == "car"
    assert latest.vehicle_bbox == [50, 100, 300, 400]
    assert latest.plate_bbox == [120, 320, 230, 360]

# 7. Test Evidence Image Creation
def test_evidence_image_creation():
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    processor = FrameProcessor()
    
    # Read frame from demo video
    source = MP4Source(DEFAULT_DEMO_VIDEO)
    source.open()
    # Read up to frame 25 where vehicle is well into view
    frame = None
    for _ in range(25):
        _, frame, _ = source.read_frame()
    source.close()
    
    assert frame is not None
    events, annotated = processor.process_frame(
        frame=frame,
        frame_number=25,
        camera_id="CAM-01",
        save_evidence=True
    )
    
    # Check if any evidence files were generated
    evidence_files = list(EVIDENCE_DIR.glob("*.*"))
    assert len(evidence_files) > 0, "Evidence images must be saved in data/evidence/"
    
    # Verify non-zero file sizes
    for f in evidence_files[:3]:
        assert f.stat().st_size > 0, f"Evidence file {f} should have non-zero size"
