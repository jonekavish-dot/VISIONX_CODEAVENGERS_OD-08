"""
Automated Test Suite for Enhanced Vehicle History, Undetected Vehicle Recovery,
and Hikvision Multi-Vehicle Detection Engine.
"""

import pytest
import numpy as np
import cv2
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from backend.app import app
from backend.schemas.detection import DetectionEvent, ProcessingStatus
from backend.database.database import (
    init_db,
    insert_vehicle_identity,
    insert_identity_observation,
    get_vehicle_history_timeline,
    get_connection
)
from backend.vehicle_identity.schemas import VehicleIdentity, IdentityObservation, IdentityEventType
from backend.vehicle_identity.identity_service import VehicleIdentityService
from backend.services.frame_processor import FrameProcessor
from backend.detection.vehicle_detector import VehicleDetector

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


def test_vehicle_history_timeline_and_dwell_time():
    """Verifies history timeline ordering, dwell time calculations, and recovery mode flags."""
    vehicle_id = "V-TEST-HIST-01"
    now = datetime.now()
    t1 = (now - timedelta(minutes=10)).isoformat()
    t2 = now.isoformat()

    # Create dummy vehicle identity
    identity = VehicleIdentity(
        vehicle_id=vehicle_id,
        canonical_plate="TN01AB1234",
        first_seen=t1,
        last_seen=t2,
        visit_count=2,
        vehicle_class="bus",
        embedding=[0.1] * 512,
        is_demo=1
    )
    insert_vehicle_identity(identity, is_demo=True)

    # Insert two observations (t1: standard detected, t2: undetected plate recovered)
    obs1 = IdentityObservation(
        vehicle_identity_id=vehicle_id,
        observed_plate="TN01AB1234",
        plate_confidence=0.92,
        ocr_confidence=0.95,
        visual_similarity=1.0,
        event_type=IdentityEventType.NEW_VEHICLE,
        camera_id="CAM-01",
        zone="GATE_IN",
        timestamp=t1,
        frame_number=10,
        is_demo=1
    )
    obs2 = IdentityObservation(
        vehicle_identity_id=vehicle_id,
        observed_plate=None,
        plate_confidence=None,
        ocr_confidence=0.0,
        visual_similarity=0.91,
        event_type=IdentityEventType.PLATE_UNREADABLE_VEHICLE_MATCH,
        camera_id="CAM-04",
        zone="GATE_OUT",
        timestamp=t2,
        frame_number=500,
        is_demo=1
    )
    insert_identity_observation(obs1, is_demo=True)
    insert_identity_observation(obs2, is_demo=True)

    timeline = get_vehicle_history_timeline(vehicle_id)
    assert len(timeline) == 2
    assert timeline[0]["observed_plate"] == "TN01AB1234"
    assert timeline[0]["recovery_mode"] == "STANDARD_PLATE_DETECTION"
    assert timeline[0]["dwell_seconds"] is None

    assert timeline[1]["observed_plate"] is None
    assert timeline[1]["recovery_mode"] == "UNDETECTED_PLATE_RECOVERED_VIA_VISUAL_REID"
    assert timeline[1]["display_plate"] == "TN01AB1234"
    assert timeline[1]["dwell_seconds"] is not None
    assert timeline[1]["dwell_seconds"] >= 590  # ~600 seconds

    # Test timeline REST API endpoint
    response = client.get(f"/api/vehicles/{vehicle_id}/timeline")
    assert response.status_code == 200
    data = response.json()
    assert data["vehicle_id"] == vehicle_id
    assert data["total_sightings"] == 2
    assert len(data["timeline"]) == 2


def test_undetected_vehicle_recovery_engine():
    """Tests recovery of vehicle identity when a vehicle returns with an undetected/unreadable plate."""
    service = VehicleIdentityService()
    
    # 1. Register baseline vehicle with a known plate TN99XX1000
    dummy_crop_1 = np.ones((100, 100, 3), dtype=np.uint8) * 150
    res1 = service.process_vehicle(
        vehicle_crop=dummy_crop_1,
        observed_plate="TN99XX1000",
        plate_confidence=0.90,
        ocr_confidence=0.95,
        vehicle_class="car",
        camera_id="CAM-01",
        zone="GATE_IN",
        is_demo=True
    )
    assigned_id = res1.vehicle_id
    assert assigned_id != ""
    assert res1.canonical_plate == "TN99XX1000"

    # 2. Process returning vehicle (same crop/embedding) but with NO PLATE detected (undetected/muddy plate)
    res2 = service.process_vehicle(
        vehicle_crop=dummy_crop_1,
        observed_plate=None,
        plate_confidence=None,
        ocr_confidence=0.0,
        vehicle_class="car",
        camera_id="CAM-02",
        zone="MATERIAL_YARD",
        is_demo=True
    )

    # Asserts deep visual Re-ID successfully identified returning vehicle
    assert res2.vehicle_id == assigned_id
    assert res2.event_type == IdentityEventType.PLATE_UNREADABLE_VEHICLE_MATCH
    assert res2.matched is True
    assert res2.canonical_plate == "TN99XX1000"
    assert "UNDETECTED_PLATE_RECOVERED" in res2.details


def test_hikvision_frame_normalization_and_multi_vehicle_detection():
    """Tests high-res Hikvision frame scaling and multi-vehicle overlay processing."""
    # 1. Test Hikvision 4K frame resolution scaling
    high_res_4k = np.zeros((2160, 3840, 3), dtype=np.uint8)
    scaled = FrameProcessor.normalize_hikvision_frame(high_res_4k, max_dim=1920)
    assert scaled.shape[1] == 1920
    assert scaled.shape[0] == 1080

    # 2. Test multi-vehicle processing pipeline
    processor = FrameProcessor()
    # Create test frame with synthetic vehicle boxes
    frame = np.full((720, 1280, 3), 200, dtype=np.uint8)
    
    events, annotated = processor.process_frame(
        frame=frame,
        frame_number=1,
        camera_id="CAM-01",
        save_evidence=False
    )
    assert len(events) >= 1
    assert annotated is not None
