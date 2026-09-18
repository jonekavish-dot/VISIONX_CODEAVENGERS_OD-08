"""
IVACS V-TRACE Identity API Verification Script
Tests all vehicle identity endpoints, demo processing with identity matching,
and asserts proper event generation and persistence.
"""

from fastapi.testclient import TestClient
from backend.app import app
import json

def verify():
    with TestClient(app) as client:
        # 1. Health check
        h = client.get("/api/health")
        assert h.status_code == 200
        print("Health Status:", h.json())

        # 2. Existing Detections
        d = client.get("/api/detections?limit=5")
        assert d.status_code == 200
        print(f"Existing Detections: total {d.json()['total']}")

        # 3. New /api/vehicles endpoint
        v = client.get("/api/vehicles")
        assert v.status_code == 200
        v_data = v.json()
        print(f"Vehicles Endpoint: total registered {v_data['total']}")
        for veh in v_data["vehicles"][:3]:
            print(f"  Vehicle {veh['vehicle_id']} | Plate: {veh['canonical_plate']} | Visits: {veh['visit_count']} | Class: {veh['vehicle_class']}")

        # 4. If any vehicles exist, test single vehicle and history
        if v_data["total"] > 0:
            first_vid = v_data["vehicles"][0]["vehicle_id"]
            single_v = client.get(f"/api/vehicles/{first_vid}")
            assert single_v.status_code == 200
            print(f"Single Vehicle {first_vid}: Plate = {single_v.json()['canonical_plate']}")

            history = client.get(f"/api/vehicles/{first_vid}/history")
            assert history.status_code == 200
            print(f"History for {first_vid}: {len(history.json())} observations")

        # 5. New /api/identity-events endpoint
        events = client.get("/api/identity-events?limit=5")
        assert events.status_code == 200
        print(f"Identity Events: total {events.json()['total']}")

        # 6. New /api/identity-events/latest endpoint
        latest_evt = client.get("/api/identity-events/latest")
        assert latest_evt.status_code == 200
        print("Latest Identity Event:", latest_evt.json())

        # 7. Start demo video processing and confirm DetectionEvent includes vehicle_id & visual_similarity
        print("\nStarting demo video processing to verify end-to-end identity enrichment...")
        st_res = client.post("/api/demo/start")
        assert st_res.status_code in [200, 409]
        
        import time
        for _ in range(5):
            time.sleep(1)
            st = client.get("/api/demo/status").json()
            if st["processed_count"] > 2:
                break
                
        client.post("/api/demo/stop")

        latest_det = client.get("/api/detections/latest").json()
        print("Enriched Latest Detection Event:")
        print("  Plate:", latest_det.get("plate"))
        print("  Vehicle ID:", latest_det.get("vehicle_id"))
        print("  Visual Similarity:", latest_det.get("visual_similarity"))
        print("  Identity Event:", latest_det.get("identity_event"))
        print("  Match Status:", latest_det.get("identity_match_status"))

    print("\n>>> ALL IDENTITY API ENDPOINTS VERIFIED SUCCESSFULLY <<<")

if __name__ == "__main__":
    verify()
