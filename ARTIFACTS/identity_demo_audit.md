# IVACS V-TRACE: Identity Demo Engine Pre-Implementation Audit

**Document:** `ARTIFACTS/identity_demo_audit.md`  
**Date:** 2026-09-18  
**Scope:** Controlled Hackathon Demonstration of Identity Mismatch & Visual Fingerprint Decision Scenarios

---

## 1. Existing Identity APIs

The existing FastAPI backend in `backend/app.py` exposes:
* `GET /api/health` — System status, runtime device (CPU/CUDA), and loaded model status.
* `GET /api/cameras` — List configured cameras (CAM-01 through CAM-04).
* `POST /api/demo/start` — Non-blocking background worker processing MP4 stream.
* `POST /api/demo/stop` — Halts background video processing.
* `GET /api/demo/status` — Live telemetry (current frame, total frames, FPS, detections count).
* `GET /api/detections` — Paginated list of detection events.
* `GET /api/detections/latest` — Latest vehicle/plate detection event.
* `GET /api/vehicles` — List of all registered vehicle identities.
* `GET /api/vehicles/{vehicle_id}` — Single vehicle identity record.
* `GET /api/vehicles/{vehicle_id}/history` — Historical observations for a vehicle.
* `GET /api/identity-events` — Paginated feed of identity match decision events.
* `GET /api/identity-events/latest` — Latest identity observation event.
* `GET /evidence/{filename}` — Static mount for evidence crops and annotated frames.

---

## 2. Existing Identity Database Tables

Persisted in `vtrace.db` (SQLite):
1. **`detections`**:
   - `id`, `camera_id`, `zone`, `timestamp`, `frame_number`, `status`
   - `vehicle_class`, `vehicle_confidence`, `plate`, `raw_plate`, `plate_confidence`, `ocr_confidence`
   - `vehicle_bbox`, `plate_bbox`, `vehicle_crop_path`, `plate_crop_path`, `frame_path`, `annotated_frame_path`
   - `vehicle_id`, `visual_similarity`, `identity_event`, `identity_match_status`, `created_at`
2. **`vehicle_identities`**:
   - `id`, `vehicle_id`, `canonical_plate`, `first_seen`, `last_seen`, `visit_count`
   - `vehicle_class`, `color`, `embedding_json`, `created_at`, `updated_at`
3. **`identity_observations`**:
   - `id`, `vehicle_identity_id`, `observed_plate`, `plate_confidence`, `ocr_confidence`
   - `visual_similarity`, `event_type`, `camera_id`, `zone`, `timestamp`, `frame_number`
   - `vehicle_crop_path`, `plate_crop_path`, `frame_path`, `previous_crop_path`

---

## 3. Existing Event Schema

In `backend/vehicle_identity/schemas.py`:
* **`IdentityEventType`**:
  - `NEW_VEHICLE`
  - `SAME_VEHICLE`
  - `POSSIBLE_IDENTITY_MISMATCH`
  - `POSSIBLE_PLATE_SWAP`
  - `PLATE_UNREADABLE_VEHICLE_MATCH`
* **`VehicleIdentity`**: Persistent identity record with 512-dim embedding.
* **`IdentityObservation`**: Historical sighting linking camera, plate, similarity, and crop evidence.
* **`IdentityMatchResult`**: Return packet from `process_vehicle(...)`.

---

## 4. Existing Evidence Paths

* Root evidence directory: `data/evidence/`
* Evidence files per detection:
  - `{camera_id}_{timestamp_slug}_f{frame_number}_v{v_idx}_frame.jpg`
  - `{camera_id}_{timestamp_slug}_f{frame_number}_v{v_idx}_vehicle.jpg`
  - `{camera_id}_{timestamp_slug}_f{frame_number}_v{v_idx}_plate.jpg`
  - `{camera_id}_{timestamp_slug}_f{frame_number}_v{v_idx}_annotated.jpg`
* Directly accessible via `/evidence/{filename}`.

---

## 5. Exact Integration Points

1. **Scenario Engine (`backend/demo/`)**:
   - `scenarios.py`: Defines deterministic 2-step media pairings for:
     - `NORMAL_REPEAT` (Same vehicle appearance + same plate => `SAME_VEHICLE`)
     - `IDENTITY_MISMATCH` (Visually different vehicle + same plate => `POSSIBLE_IDENTITY_MISMATCH`)
     - `PLATE_SWAP` (Same vehicle appearance + different plate => `POSSIBLE_PLATE_SWAP`)
     - `PLATE_UNREADABLE` (Same vehicle appearance + unreadable plate => `PLATE_UNREADABLE_VEHICLE_MATCH`)
   - `scenario_manager.py`: Controls step execution, feeds images through the **real** `VehicleIdentityService` and ResNet18 feature extractor (zero synthetic scores), enforces cooldown deduplication, and exposes scenario state.
2. **Temporal Deduplication**:
   - Maintain `IDENTITY_EVENT_COOLDOWN_SECONDS` (default 5s). Observations of the same plate + identity within the cooldown window update timestamps without emitting duplicate alert events.
3. **Demo Isolation & Reset**:
   - Add `is_demo` flag in `detections`, `vehicle_identities`, and `identity_observations` (non-breaking migration).
   - `POST /api/demo/reset` safely removes only records where `is_demo = 1` and cleans demo evidence crops.
4. **New API Endpoints**:
   - `POST /api/demo/scenario/start`
   - `POST /api/demo/scenario/stop`
   - `GET /api/demo/scenario/status`
   - `GET /api/identity-events/{id}`
   - `GET /api/vehicles/{id}/comparison`
   - `POST /api/demo/reset`

---

## 6. Files to Be Created & Modified

### New Files:
* `ARTIFACTS/identity_demo_audit.md` (This document)
* `ARTIFACTS/demo_scenarios.md` (Scenario definitions and expected outputs)
* `ARTIFACTS/identity_demo_validation.md` (Final validation test log)
* `backend/demo/__init__.py`
* `backend/demo/scenarios.py`
* `backend/demo/scenario_manager.py`
* `scripts/setup_demo_media.py` (Prepares demo scenario media locally)
* `tests/test_demo_scenarios.py` (8 new scenario tests)

### Modified Files:
* `backend/config.py` (Add `IDENTITY_EVENT_COOLDOWN_SECONDS`, scenario media paths)
* `backend/database/database.py` (Add `is_demo` column, reset demo data, fetch observation by id, fetch vehicle comparison)
* `backend/vehicle_identity/schemas.py` (Add comparison schema and alert text models)
* `backend/vehicle_identity/identity_service.py` (Support `is_demo` tagging and temporal cooldown)
* `backend/app.py` (Expose scenario management, comparison, and reset endpoints)
* `report_generator.py` (Reflect demo scenario engine in PDF)
