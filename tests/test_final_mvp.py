"""
IVACS V-TRACE Final MVP Verification Test Suite
Verifies all 15 required MVP capabilities:
1. demo registry lookup
2. unknown registry vehicle
3. registry attribute match
4. registry attribute mismatch
5. valid permit
6. expired permit
7. unauthorized zone
8. valid route
9. impossible route
10. dashboard summary
11. alert creation
12. alert deduplication
13. trust snapshot
14. complete identity mismatch flow
15. complete plate swap flow
"""

import os
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from backend.app import app
from backend.vehicle_registry import (
    VehicleRegistryService,
    RegistryConsistencyStatus
)
from backend.site_context import (
    PermitManager,
    RouteIntegrityChecker,
    PermitCheckStatus,
    RouteStatus
)
from backend.alerts import (
    AlertService,
    AlertType,
    AlertSeverity
)
from backend.database.database import (
    init_db,
    reset_demo_data,
    reset_demo_registry_data
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    init_db()
    yield


# 1. Demo Registry Lookup
def test_demo_registry_lookup():
    response = client.get("/api/registry/vehicle/TN01AB1234")
    assert response.status_code == 200
    data = response.json()
    assert data["plate"] == "TN01AB1234"
    assert data["manufacturer"] == "Tata"
    assert data["model"] == "Starbus"
    assert data["vehicle_type"] == "bus"
    assert data["source"] == "DEMO_REGISTRY"
    assert data["is_demo"] is True


# 2. Unknown Registry Vehicle
def test_unknown_registry_vehicle():
    response = client.get("/api/registry/vehicle/ZZ99XX0000")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# 3. Registry Attribute Match
def test_registry_attribute_match():
    reg_service = VehicleRegistryService()
    result = reg_service.check_consistency("TN01AB1234", observed_class="bus", observed_colour="WHITE")
    assert result.status == RegistryConsistencyStatus.REGISTRY_MATCH
    assert len(result.mismatched_attributes) == 0
    assert result.record is not None


# 4. Registry Attribute Mismatch
def test_registry_attribute_mismatch():
    reg_service = VehicleRegistryService()
    # TN01AB1234 is registered as a bus (Starbus), but observed as a truck
    result = reg_service.check_consistency("TN01AB1234", observed_class="truck")
    assert result.status == RegistryConsistencyStatus.REGISTRY_ATTRIBUTE_MISMATCH
    assert any("vehicle_class" in m for m in result.mismatched_attributes)



# 5. Valid Permit
def test_valid_permit():
    permit_mgr = PermitManager()
    res = permit_mgr.check_permit("TN01AB1234", current_zone="GATE_IN")
    assert res.status == PermitCheckStatus.AUTHORIZED
    assert "GATE_IN" in res.allowed_zones


# 6. Expired Permit
def test_expired_permit():
    permit_mgr = PermitManager()
    # KA01AB1234 has an EXPIRED permit seeded in DB
    res = permit_mgr.check_permit("KA01AB1234", current_zone="GATE_IN")
    assert res.status == PermitCheckStatus.PERMIT_EXPIRED
    assert res.permit is not None


# 7. Unauthorized Zone
def test_unauthorized_zone():
    permit_mgr = PermitManager()
    # DL01XY9999 has allowed_zones: ["GATE_IN", "MATERIAL_YARD"] only
    res = permit_mgr.check_permit("DL01XY9999", current_zone="ACTIVE_ZONE")
    assert res.status == PermitCheckStatus.UNAUTHORIZED_ZONE
    assert "ACTIVE_ZONE" not in res.allowed_zones


# 8. Valid Route
def test_valid_route():
    checker = RouteIntegrityChecker()
    veh_id = "V-TEST-VAL-ROUTE"
    # Step 1: At GATE_IN
    res1 = checker.check_route(veh_id, "TN01AB1234", "CAM-01", "GATE_IN", "2026-09-18T10:00:00", is_demo=True)
    assert res1.status == RouteStatus.NORMAL
    # Step 2: At MATERIAL_YARD 20 seconds later (minimum rule: 10s)
    res2 = checker.check_route(veh_id, "TN01AB1234", "CAM-02", "MATERIAL_YARD", "2026-09-18T10:00:20", is_demo=True)
    assert res2.status == RouteStatus.NORMAL
    assert res2.is_anomaly is False


# 9. Impossible Route
def test_impossible_route():
    checker = RouteIntegrityChecker()
    veh_id = "V-TEST-IMP-ROUTE"
    # Step 1: At MATERIAL_YARD
    res1 = checker.check_route(veh_id, "TN01AB1234", "CAM-02", "MATERIAL_YARD", "2026-09-18T10:00:00", is_demo=True)
    assert res1.status == RouteStatus.NORMAL
    # Step 2: At GATE_OUT only 2 seconds later (configured minimum: 30s)
    res2 = checker.check_route(veh_id, "TN01AB1234", "CAM-04", "GATE_OUT", "2026-09-18T10:00:02", is_demo=True)
    assert res2.status == RouteStatus.ROUTE_INTEGRITY_ANOMALY
    assert res2.is_anomaly is True
    assert "minimum" in res2.reason.lower()


# 10. Dashboard Summary
def test_dashboard_summary():
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    data = response.json()
    assert "active_vehicles" in data
    assert "detections" in data
    assert "identity_warnings" in data
    assert "access_alerts" in data
    assert "route_alerts" in data
    assert "unreadable_plates" in data
    assert isinstance(data["active_vehicles"], int)


# 11. Alert Creation
def test_alert_creation():
    alert_svc = AlertService(cooldown_seconds=0)
    alert = alert_svc.create_alert(
        alert_type=AlertType.UNAUTHORIZED_ZONE.value,
        camera_id="CAM-03",
        zone="ACTIVE_ZONE",
        plate="DL01XY9999",
        vehicle_id="V-TEST-AL1",
        details="Restricted vehicle entered active zone",
        is_demo=True
    )
    assert alert is not None
    assert alert.severity == AlertSeverity.CRITICAL.value
    assert alert.id is not None

    # Fetch via API
    resp = client.get(f"/api/alerts/{alert.id}")
    assert resp.status_code == 200
    assert resp.json()["type"] == AlertType.UNAUTHORIZED_ZONE.value


# 12. Alert Deduplication
def test_alert_deduplication():
    alert_svc = AlertService(cooldown_seconds=10)
    alert_svc.clear_cooldown()

    # First call creates alert
    al1 = alert_svc.create_alert(
        alert_type=AlertType.POSSIBLE_IDENTITY_MISMATCH.value,
        camera_id="CAM-01",
        zone="GATE_IN",
        plate="TN01AB1234",
        vehicle_id="V-TEST-DEDUP",
        similarity=0.25,
        is_demo=True
    )
    assert al1 is not None

    # Immediate second call with same vehicle & type should be suppressed
    al2 = alert_svc.create_alert(
        alert_type=AlertType.POSSIBLE_IDENTITY_MISMATCH.value,
        camera_id="CAM-01",
        zone="GATE_IN",
        plate="TN01AB1234",
        vehicle_id="V-TEST-DEDUP",
        similarity=0.25,
        is_demo=True
    )
    assert al2 is None


# 13. Trust Snapshot
def test_trust_snapshot():
    # First trigger normal repeat to populate an identity
    start_resp = client.post("/api/demo/scenario/start", json={"scenario": "NORMAL_REPEAT"})
    assert start_resp.status_code == 200
    st = start_resp.json()
    veh_id = st["current_observation"]["vehicle_identity_id"]

    # Fetch trust snapshot
    snap_resp = client.get(f"/api/vehicles/{veh_id}/trust-snapshot")
    assert snap_resp.status_code == 200
    snap = snap_resp.json()
    assert snap["vehicle_id"] == veh_id
    assert snap["overall_event"] in ["NORMAL", "IDENTITY_INCONSISTENCY", "REGISTRY_MISMATCH"]
    assert "visual_similarity" in snap
    assert "registry_status" in snap
    assert "permit_status" in snap
    assert "route_status" in snap


# 14. Complete Identity Mismatch Flow
def test_complete_identity_mismatch_flow():
    # Reset previous demo records
    reset_resp = client.post("/api/demo/reset")
    assert reset_resp.status_code == 200

    # Start IDENTITY_MISMATCH scenario
    start_resp = client.post("/api/demo/scenario/start", json={"scenario": "IDENTITY_MISMATCH"})
    assert start_resp.status_code == 200
    data = start_resp.json()
    assert data["status"] == "COMPLETED"
    assert data["step"] == 2

    comp = data["comparison"]
    assert comp is not None
    assert comp["identity_event"] == "POSSIBLE_IDENTITY_MISMATCH"
    assert comp["requires_manual_review"] is True
    assert comp["visual_similarity"] < 0.85
    assert os.path.exists(comp["current_vehicle_image"])
    assert os.path.exists(comp["historical_vehicle_image"])

    # Verify side-by-side comparison endpoint
    veh_id = comp["vehicle_id"]
    comp_resp = client.get(f"/api/vehicles/{veh_id}/comparison")
    assert comp_resp.status_code == 200
    assert comp_resp.json()["identity_event"] == "POSSIBLE_IDENTITY_MISMATCH"

    # Verify alert was generated
    alerts_resp = client.get("/api/alerts?alert_type=POSSIBLE_IDENTITY_MISMATCH")
    assert alerts_resp.status_code == 200
    assert len(alerts_resp.json()) >= 1


# 15. Complete Plate Swap Flow
def test_complete_plate_swap_flow():
    # Reset previous demo records
    reset_resp = client.post("/api/demo/reset")
    assert reset_resp.status_code == 200

    # Start PLATE_SWAP scenario
    start_resp = client.post("/api/demo/scenario/start", json={"scenario": "PLATE_SWAP"})
    assert start_resp.status_code == 200
    data = start_resp.json()
    assert data["status"] == "COMPLETED"

    comp = data["comparison"]
    assert comp is not None
    assert comp["identity_event"] == "POSSIBLE_PLATE_SWAP"
    assert comp["visual_similarity"] >= 0.85
