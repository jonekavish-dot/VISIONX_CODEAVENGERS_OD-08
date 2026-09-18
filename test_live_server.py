"""
Tests all live endpoints against the active running Uvicorn server on http://127.0.0.1:8000
"""

import requests
import time
import os

BASE_URL = "http://127.0.0.1:8000"

def test_live():
    print("=== 1. Testing GET /api/health ===")
    r = requests.get(f"{BASE_URL}/api/health", timeout=5)
    print("Status:", r.status_code)
    print("Response:", r.json())
    assert r.status_code == 200

    print("\n=== 2. Testing GET /api/cameras ===")
    r = requests.get(f"{BASE_URL}/api/cameras", timeout=5)
    print("Status:", r.status_code)
    cameras = r.json()
    print("Cameras count:", len(cameras))
    for cam in cameras:
        print(f"  {cam['id']} - {cam['name']} ({cam['zone']})")
    assert r.status_code == 200

    print("\n=== 3. Testing POST /api/demo/start ===")
    r = requests.post(f"{BASE_URL}/api/demo/start", timeout=5)
    print("Status:", r.status_code)
    print("Response:", r.json())
    # 200 or 409 if already processing
    assert r.status_code in [200, 409]

    print("\n=== 4. Monitoring Live Stream via GET /api/demo/status ===")
    for i in range(8):
        time.sleep(1)
        st = requests.get(f"{BASE_URL}/api/demo/status", timeout=5).json()
        print(f"[{i+1}s] Running: {st['is_running']} | Frame: {st['current_frame']}/{st['total_frames']} | Processed: {st['processed_count']} | Detections: {st['detections_count']} | FPS: {st['fps']}")

    print("\n=== 5. Testing GET /api/detections ===")
    r = requests.get(f"{BASE_URL}/api/detections?limit=5", timeout=5)
    print("Status:", r.status_code)
    data = r.json()
    print(f"Total in DB: {data['total']}, Showing: {len(data['detections'])}")
    assert r.status_code == 200

    print("\n=== 6. Testing GET /api/detections/latest ===")
    r = requests.get(f"{BASE_URL}/api/detections/latest", timeout=5)
    print("Status:", r.status_code)
    latest = r.json()
    assert latest is not None
    print("Latest Detection:")
    print("  ID:", latest["id"])
    print("  Camera:", latest["camera_id"], f"({latest['zone']})")
    print("  Vehicle:", latest["vehicle_class"], f"(confidence: {latest['vehicle_confidence']})")
    print("  Plate:", latest["plate"], f"(raw: {latest['raw_plate']})")
    print("  OCR Conf:", latest["ocr_confidence"])
    print("  BBox Vehicle:", latest["vehicle_bbox"])
    print("  BBox Plate:", latest["plate_bbox"])
    print("  Plate Crop Path:", latest["plate_crop_path"])

    print("\n=== 7. Testing Static Evidence Access (/evidence/{filename}) ===")
    if latest.get("plate_crop_path"):
        filename = os.path.basename(latest["plate_crop_path"])
        r = requests.get(f"{BASE_URL}/evidence/{filename}", timeout=5)
        print(f"Fetching /evidence/{filename}: Status {r.status_code}, Length: {len(r.content)} bytes")
        assert r.status_code == 200
        assert len(r.content) > 0

    print("\n>>> LIVE SERVER VALIDATION COMPLETED WITH 100% SUCCESS <<<")

if __name__ == "__main__":
    test_live()
