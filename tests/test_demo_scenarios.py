"""
IVACS V-TRACE Demo Scenarios Test Suite
Validates the 4 controlled demonstration scenarios, scenario manager state machine,
comparison endpoint, demo data reset, and temporal deduplication cooldown.
"""

import os
import time
import pytest
import numpy as np
from fastapi.testclient import TestClient

from backend.app import app
from backend.demo.scenario_manager import ScenarioManager
from backend.vehicle_identity.schemas import (
    IdentityEventType,
    ScenarioStatus,
    VehicleComparisonResponse
)
from backend.vehicle_identity.identity_service import VehicleIdentityService
from backend.database.database import (
    get_connection,
    get_all_identity_observations,
    get_identity_observations_for_vehicle
)

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def scenario_mgr():
    mgr = ScenarioManager()
    mgr.reset_demo()
    yield mgr
    mgr.reset_demo()

# Test 1: Normal Repeat Scenario
def test_scenario_normal_repeat(scenario_mgr):
    status = scenario_mgr.start_scenario("NORMAL_REPEAT")
    assert status.status == ScenarioStatus.COMPLETED
    assert status.step == 2
    assert status.comparison is not None
    assert status.comparison.identity_event == IdentityEventType.SAME_VEHICLE.value
    assert status.comparison.visual_similarity >= 0.85
    assert status.comparison.requires_manual_review is False
    assert "Rule A" in status.comparison.rule_used

# Test 2: Identity Mismatch Scenario (Core Innovation Demonstration)
def test_scenario_identity_mismatch(scenario_mgr):
    status = scenario_mgr.start_scenario("IDENTITY_MISMATCH")
    assert status.status == ScenarioStatus.COMPLETED
    assert status.step == 2
    assert status.comparison is not None
    assert status.comparison.identity_event == IdentityEventType.POSSIBLE_IDENTITY_MISMATCH.value
    assert status.comparison.visual_similarity < 0.85
    assert status.comparison.requires_manual_review is True
    assert "Rule B" in status.comparison.rule_used
    assert "POSSIBLE" in status.comparison.alert_title
    # Verify both vehicle images exist
    assert os.path.exists(status.comparison.current_vehicle_image)
    assert os.path.exists(status.comparison.historical_vehicle_image)

# Test 3: Plate Swap Scenario
def test_scenario_plate_swap(scenario_mgr):
    status = scenario_mgr.start_scenario("PLATE_SWAP")
    assert status.status == ScenarioStatus.COMPLETED
    assert status.step == 2
    assert status.comparison is not None
    assert status.comparison.identity_event == IdentityEventType.POSSIBLE_PLATE_SWAP.value
    assert status.comparison.visual_similarity >= 0.85
    assert status.comparison.requires_manual_review is True
    assert "Rule C" in status.comparison.rule_used

# Test 4: Plate Unreadable Scenario
def test_scenario_unreadable_plate(scenario_mgr):
    status = scenario_mgr.start_scenario("PLATE_UNREADABLE")
    assert status.status == ScenarioStatus.COMPLETED
    assert status.step == 2
    assert status.comparison is not None
    assert status.comparison.identity_event == IdentityEventType.PLATE_UNREADABLE_VEHICLE_MATCH.value
    assert status.comparison.visual_similarity >= 0.85
    assert status.comparison.requires_manual_review is False
    assert "Rule D" in status.comparison.rule_used

# Test 5: Scenario Start/Stop State Machine
def test_scenario_start_stop(scenario_mgr):
    status = scenario_mgr.start_scenario("IDENTITY_MISMATCH")
    assert status.status == ScenarioStatus.COMPLETED
    scenario_mgr.stop_scenario()
    status_stopped = scenario_mgr.get_scenario_status()
    assert status_stopped.status == ScenarioStatus.IDLE

# Test 6: Demo Scenario Reset
def test_scenario_reset(scenario_mgr):
    # Run a scenario to populate demo records
    scenario_mgr.start_scenario("IDENTITY_MISMATCH")
    
    # Check that demo records exist in database
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM identity_observations WHERE is_demo = 1")
    demo_count_before = c.fetchone()[0]
    conn.close()
    assert demo_count_before >= 1
    
    # Perform reset
    stats = scenario_mgr.reset_demo()
    assert stats["deleted_observations"] >= 1
    assert stats["deleted_vehicles"] >= 1
    
    # Confirm demo records are now 0
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM identity_observations WHERE is_demo = 1")
    demo_count_after = c.fetchone()[0]
    conn.close()
    assert demo_count_after == 0

# Test 7: Comparison API via FastAPI TestClient
def test_comparison_api(client):
    # Start scenario via REST API
    res = client.post("/api/demo/scenario/start", json={"scenario": "IDENTITY_MISMATCH"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert data["step"] == 2
    
    comp = data["comparison"]
    assert comp is not None
    v_id = comp["vehicle_id"]
    
    # Query GET /api/vehicles/{id}/comparison
    comp_res = client.get(f"/api/vehicles/{v_id}/comparison")
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    assert comp_data["vehicle_id"] == v_id
    assert comp_data["identity_event"] == "POSSIBLE_IDENTITY_MISMATCH"
    assert comp_data["requires_manual_review"] is True
    assert comp_data["visual_similarity"] < 0.85
    assert comp_data["current_vehicle_image"] is not None
    assert comp_data["historical_vehicle_image"] is not None
    
    # Query latest identity event
    latest_res = client.get("/api/identity-events/latest")
    assert latest_res.status_code == 200
    latest_evt = latest_res.json()
    assert latest_evt is not None
    assert latest_evt["event_type"] == "POSSIBLE_IDENTITY_MISMATCH"
    
    # Query single event by ID
    evt_id = latest_evt["id"]
    single_evt = client.get(f"/api/identity-events/{evt_id}")
    assert single_evt.status_code == 200
    assert single_evt.json()["id"] == evt_id
    
    # Reset demo data via API
    reset_res = client.post("/api/demo/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "success"

# Test 8: Duplicate Identity Event Suppression (Temporal Deduplication)
def test_duplicate_identity_event_suppression():
    service = VehicleIdentityService()
    service.clear_cooldown()
    
    dummy_crop = np.full((100, 100, 3), 128, dtype=np.uint8)
    plate_str = f"TEST_DEDUP_{int(time.time())}"
    
    # First sighting -> new vehicle
    res1 = service.process_vehicle(
        vehicle_crop=dummy_crop,
        observed_plate=plate_str,
        plate_confidence=0.9,
        ocr_confidence=0.9,
        is_demo=True
    )
    assert res1.is_duplicate is False
    v_id = res1.vehicle_id
    
    # Immediate second sighting with same vehicle crop and plate (within 5s cooldown)
    res2 = service.process_vehicle(
        vehicle_crop=dummy_crop,
        observed_plate=plate_str,
        plate_confidence=0.9,
        ocr_confidence=0.9,
        is_demo=True
    )
    # The duplicate identity observation should be suppressed
    assert res2.is_duplicate is True
    
    # Verify that only 1 observation is logged for this vehicle
    obs_list = get_identity_observations_for_vehicle(v_id)
    assert len(obs_list) == 1
