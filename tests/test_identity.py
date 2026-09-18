"""
IVACS V-TRACE Vehicle Identity & Visual Fingerprint Test Suite
Deterministic unit and integration tests covering all 5 core decision rules:
1. NEW_VEHICLE (Rule E)
2. SAME_VEHICLE (Rule A)
3. POSSIBLE_IDENTITY_MISMATCH (Rule B)
4. POSSIBLE_PLATE_SWAP (Rule C)
5. PLATE_UNREADABLE_VEHICLE_MATCH (Rule D)
Independent of internet downloads.
"""

import pytest
import numpy as np
import cv2

from backend.config import IDENTITY_HIGH_THRESHOLD, IDENTITY_LOW_THRESHOLD
from backend.vehicle_identity.schemas import IdentityEventType
from backend.vehicle_identity.similarity import cosine_similarity
from backend.vehicle_identity.identity_rules import evaluate_identity_decision
from backend.vehicle_identity.feature_extractor import VehicleFeatureExtractor
from backend.vehicle_identity.identity_service import VehicleIdentityService
from backend.database.database import init_db

# Fixtures for deterministic test images
@pytest.fixture(scope="module")
def feature_extractor():
    return VehicleFeatureExtractor(device="cpu")

@pytest.fixture(scope="module")
def vehicle_crop_a():
    # Blue truck/vehicle pattern
    img = np.zeros((160, 200, 3), dtype=np.uint8)
    img[:] = (180, 80, 20)  # Blue-ish BGR
    cv2.rectangle(img, (20, 20), (180, 80), (220, 180, 50), -1)  # Windshield
    cv2.circle(img, (40, 130), 20, (15, 15, 15), -1)             # Left Wheel
    cv2.circle(img, (160, 130), 20, (15, 15, 15), -1)            # Right Wheel
    return img

@pytest.fixture(scope="module")
def vehicle_crop_a_variant(vehicle_crop_a):
    # Same vehicle with slight lighting/crop variation (high similarity ~ 0.95+)
    variant = vehicle_crop_a.copy()
    noise = np.random.normal(0, 3, variant.shape).astype(np.int16)
    noisy = np.clip(variant.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return noisy

@pytest.fixture(scope="module")
def vehicle_crop_b():
    # Red sports car/van pattern (clearly distinct appearance)
    img = np.zeros((160, 200, 3), dtype=np.uint8)
    img[:] = (20, 20, 200)  # Red BGR
    cv2.rectangle(img, (40, 50), (160, 120), (240, 240, 240), -1) # White racing stripe
    cv2.rectangle(img, (10, 80), (190, 140), (40, 40, 40), -1)    # Dark lower body
    return img

# 1. Cosine Similarity Unit Tests
def test_cosine_similarity_basics():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v2), 0.001) == 1.0

    v_orth = [0.0, 1.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v_orth), 0.001) == 0.0

    assert cosine_similarity(None, v1) == 0.0
    assert cosine_similarity([], v1) == 0.0

# 2. Rule E: NEW_VEHICLE
def test_rule_new_vehicle():
    event, detail = evaluate_identity_decision(
        observed_plate="TN01AB1234",
        candidate_plate=None,
        visual_similarity=0.0
    )
    assert event == IdentityEventType.NEW_VEHICLE
    assert "new vehicle" in detail.lower()

# 3. Rule A: SAME_VEHICLE
def test_rule_same_vehicle():
    event, detail = evaluate_identity_decision(
        observed_plate="TN01AB1234",
        candidate_plate="TN01AB1234",
        visual_similarity=0.92
    )
    assert event == IdentityEventType.SAME_VEHICLE
    assert "consistent" in detail.lower()

# 4. Rule B: POSSIBLE_IDENTITY_MISMATCH
def test_rule_possible_identity_mismatch():
    event, detail = evaluate_identity_decision(
        observed_plate="TN01AB1234",
        candidate_plate="TN01AB1234",
        visual_similarity=0.35
    )
    assert event == IdentityEventType.POSSIBLE_IDENTITY_MISMATCH
    assert "deviates" in detail.lower() or "mismatch" in detail.lower()

# 5. Rule C: POSSIBLE_PLATE_SWAP
def test_rule_possible_plate_swap():
    event, detail = evaluate_identity_decision(
        observed_plate="MH12DE1433",
        candidate_plate="TN01AB1234",
        visual_similarity=0.91
    )
    assert event == IdentityEventType.POSSIBLE_PLATE_SWAP
    assert "plate swap" in detail.lower()

# 6. Rule D: PLATE_UNREADABLE_VEHICLE_MATCH
def test_rule_plate_unreadable_vehicle_match():
    event, detail = evaluate_identity_decision(
        observed_plate=None,
        candidate_plate="TN01AB1234",
        visual_similarity=0.88
    )
    assert event == IdentityEventType.PLATE_UNREADABLE_VEHICLE_MATCH
    assert "unreadable" in detail.lower()

import uuid

# 7. End-to-End Service Integration Test covering all 5 Lifecycle Scenarios
def test_service_identity_lifecycle(feature_extractor, vehicle_crop_a, vehicle_crop_a_variant, vehicle_crop_b):
    init_db()
    service = VehicleIdentityService(feature_extractor=feature_extractor)
    # Start with fresh in-memory identity list for this test lifecycle
    service._identities = []

    unique_suffix = uuid.uuid4().hex[:4].upper()
    test_plate = f"TN99AA{unique_suffix}"
    swap_plate = f"DL99BB{unique_suffix}"

    # 1. NEW_VEHICLE: Register vehicle A under unique test_plate
    res1 = service.process_vehicle(
        vehicle_crop=vehicle_crop_a,
        observed_plate=test_plate,
        plate_confidence=0.90,
        ocr_confidence=0.95,
        vehicle_class="truck"
    )
    assert res1.event_type == IdentityEventType.NEW_VEHICLE
    assert res1.vehicle_id.startswith("V-")
    veh_a_id = res1.vehicle_id

    # 2. SAME_VEHICLE: Same vehicle A variant observed with same test_plate
    res2 = service.process_vehicle(
        vehicle_crop=vehicle_crop_a_variant,
        observed_plate=test_plate,
        plate_confidence=0.88,
        ocr_confidence=0.93,
        vehicle_class="truck"
    )
    assert res2.event_type == IdentityEventType.SAME_VEHICLE
    assert res2.matched is True
    assert res2.vehicle_id == veh_a_id
    assert res2.similarity >= IDENTITY_HIGH_THRESHOLD

    # 3. POSSIBLE_IDENTITY_MISMATCH: Different vehicle (crop B) observed claiming test_plate
    res3 = service.process_vehicle(
        vehicle_crop=vehicle_crop_b,
        observed_plate=test_plate,
        plate_confidence=0.85,
        ocr_confidence=0.90,
        vehicle_class="car"
    )
    assert res3.event_type == IdentityEventType.POSSIBLE_IDENTITY_MISMATCH
    assert res3.matched is False
    assert res3.similarity < IDENTITY_HIGH_THRESHOLD

    # 4. POSSIBLE_PLATE_SWAP: Vehicle A variant observed with a DIFFERENT plate (swap_plate)
    res4 = service.process_vehicle(
        vehicle_crop=vehicle_crop_a_variant,
        observed_plate=swap_plate,
        plate_confidence=0.89,
        ocr_confidence=0.92,
        vehicle_class="truck"
    )
    assert res4.event_type == IdentityEventType.POSSIBLE_PLATE_SWAP
    assert res4.matched is False
    assert res4.similarity >= IDENTITY_HIGH_THRESHOLD

    # 5. PLATE_UNREADABLE_VEHICLE_MATCH: Vehicle A variant observed with NO plate (OCR unreadable)
    res5 = service.process_vehicle(
        vehicle_crop=vehicle_crop_a_variant,
        observed_plate=None,
        plate_confidence=None,
        ocr_confidence=None,
        vehicle_class="truck"
    )
    assert res5.event_type == IdentityEventType.PLATE_UNREADABLE_VEHICLE_MATCH
    assert res5.matched is True
    assert res5.vehicle_id == veh_a_id
    assert res5.similarity >= IDENTITY_HIGH_THRESHOLD
