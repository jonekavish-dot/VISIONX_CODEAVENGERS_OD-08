"""
IVACS V-TRACE Live API & Demo Verification Script
Starts FastAPI test client, triggers demo processing, verifies endpoints,
and asserts SQLite records and evidence storage.
"""

import time
import sys
from fastapi.testclient import TestClient
from backend.app import app
from backend.database.database import get_total_detections_count, get_latest_detection

def run_verification():
    print("=== Step 1: Starting FastAPI Client ===")
    with TestClient(app) as client:
        # 1. Health check
        h_res = client.get("/api/health")
        print("Health Status:", h_res.status_code, h_res.json())
        assert h_res.status_code == 200, "Health endpoint failed"
        assert h_res.json()["status"] == "healthy"

        # 2. Cameras endpoint
        c_res = client.get("/api/cameras")
        print("Cameras Status:", c_res.status_code, f"Loaded {len(c_res.json())} cameras")
        assert c_res.status_code == 200

        # 3. Start Demo
        print("\n=== Step 2: Triggering POST /api/demo/start ===")
        start_res = client.post("/api/demo/start")
        print("Start Demo Status:", start_res.status_code, start_res.json())
        assert start_res.status_code == 200

        # 4. Monitor Demo Status
        print("\n=== Step 3: Polling GET /api/demo/status ===")
        for i in range(12):
            time.sleep(1)
            status_res = client.get("/api/demo/status")
            st = status_res.json()
            curr = st.get("current_frame", 0)
            total = st.get("total_frames", 0)
            proc = st.get("processed_count", 0)
            dets = st.get("detections_count", 0)
            fps = st.get("fps", 0.0)
            is_run = st.get("is_running", False)
            print(f"[{i+1}s] Running: {is_run} | Frame: {curr}/{total} | Processed: {proc} | Detections: {dets} | FPS: {fps:.1f}")
            if not is_run and proc > 0:
                break

        # Stop demo if still running
        client.post("/api/demo/stop")

        # 5. Check Detections
        print("\n=== Step 4: GET /api/detections ===")
        d_res = client.get("/api/detections?limit=10")
        assert d_res.status_code == 200
        d_data = d_res.json()
        print(f"Total detections returned: {d_data['total']}, Items in page: {len(d_data['detections'])}")

        # 6. Check Latest Detection
        print("\n=== Step 5: GET /api/detections/latest ===")
        lat_res = client.get("/api/detections/latest")
        assert lat_res.status_code == 200
        latest_obj = lat_res.json()
        print("Latest Event from API:", latest_obj)

    print("\n=== Step 6: Direct SQLite Verification ===")
    total_db = get_total_detections_count()
    print(f"Total SQLite rows in detections table: {total_db}")
    assert total_db > 0, "Detections table must contain at least 1 record"

    latest_db = get_latest_detection()
    print("Latest DB Object:")
    print(f"  Camera: {latest_db.camera_id} ({latest_db.zone})")
    print(f"  Vehicle: {latest_db.vehicle_class} (confidence: {latest_db.vehicle_confidence})")
    print(f"  Plate: {latest_db.plate}")
    print(f"  Raw Plate: {latest_db.raw_plate}")
    print(f"  OCR Confidence: {latest_db.ocr_confidence}")
    print(f"  Vehicle BBox: {latest_db.vehicle_bbox}")
    print(f"  Plate BBox: {latest_db.plate_bbox}")
    print(f"  Frame Crop Path: {latest_db.frame_path}")
    print(f"  Vehicle Crop Path: {latest_db.vehicle_crop_path}")
    print(f"  Plate Crop Path: {latest_db.plate_crop_path}")

    print("\n=== ALL VERIFICATION CHECKS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_verification()
