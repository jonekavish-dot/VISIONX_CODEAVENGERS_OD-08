# IVACS V-TRACE: Pre-Implementation Audit for Final MVP (OD-08)

## 1. Existing Working Functionality

The repository contains an end-to-end native computer vision pipeline for Problem Statement OD-08:
1. **Video Ingestion Layer** (`backend/video/`): Stream abstraction supporting MP4 video files, RTSP streams, and USB webcams with configurable frame stride (`PROCESS_EVERY_N_FRAMES`).
2. **Vehicle Detection Engine** (`backend/detection/vehicle_detector.py`): Ultralytics YOLOv8n object detector filtering target COCO classes (car, truck, bus, motorcycle) with bounding box normalization and confidence thresholding (`VEHICLE_CONF_THRESHOLD = 0.40`).
3. **Plate Localization Engine** (`backend/detection/plate_detector.py`): Bumper-ROI heuristic search, morphological gradient enhancement, rectangular contour detection, and spatial vehicle-to-plate association.
4. **OCR Character Recognition** (`backend/ocr/plate_ocr.py`): EasyOCR text reader with Indian state code validation, IND blue-strip cropping, slot normalization (e.g. O->0, I->1 in numeric slots), and confidence scoring.
5. **Vehicle Visual Fingerprint Engine** (`backend/vehicle_identity/`): ResNet18 convolutional backbone extracting 512-dimensional L2-normalized feature embeddings from vehicle crops.
6. **Deterministic Identity Rules A–E** (`backend/vehicle_identity/identity_rules.py`):
   - **Rule A:** Same Plate + High Similarity ($\ge 0.85$) $\rightarrow$ `SAME_VEHICLE`
   - **Rule B:** Same Plate + Low Similarity ($< 0.85$) $\rightarrow$ `POSSIBLE_IDENTITY_MISMATCH`
   - **Rule C:** Different Plate + High Similarity ($\ge 0.85$) $\rightarrow$ `POSSIBLE_PLATE_SWAP`
   - **Rule D:** Plate Unreadable + High Similarity ($\ge 0.85$) $\rightarrow$ `PLATE_UNREADABLE_VEHICLE_MATCH`
   - **Rule E:** No Historical Match $\rightarrow$ `NEW_VEHICLE`
7. **Temporal Deduplication** (`backend/vehicle_identity/identity_service.py`): 5-second cooldown suppression keyed on `(assigned_vehicle_id, clean_plate, event_type)` preventing event flood.
8. **Controlled 4-Scenario Demo Engine** (`backend/demo/`): Executes deterministic 2-step scenarios (`NORMAL_REPEAT`, `IDENTITY_MISMATCH`, `PLATE_SWAP`, `PLATE_UNREADABLE`) through genuine ResNet18 neural embeddings without synthetic scores.
9. **Evidence Storage & Retrieval** (`data/evidence/` and `data/demo/scenarios/`): Multi-scale disk storage for full frames, vehicle crops, plate crops, and annotated bounding box frames.
10. **Evidence Comparison Endpoint** (`backend/app.py`): `GET /api/vehicles/{vehicle_id}/comparison` returning current vs. historical vehicle and plate crops, similarity score, and analytical text templates.
11. **Isolated Demo Reset** (`POST /api/demo/reset`): Purges only records where `is_demo = 1`, preserving database structure and production data.
12. **Automated QA Suite** (`tests/`): 22/22 unit and integration tests passing in 29.17s.

---

## 2. Reusable Existing APIs

The existing FastAPI server (`backend/app.py`) provides 18 verified endpoints:

| Method | Route | Description | Status |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | Service health, compute device (CPU/CUDA), and model status | Active |
| `GET` | `/api/cameras` | List configured construction site CCTV cameras (CAM-01 to CAM-04) | Active |
| `POST` | `/api/demo/start` | Launch background video processing on demo video stream | Active |
| `POST` | `/api/demo/stop` | Stop background video processing | Active |
| `GET` | `/api/demo/status` | Video streaming telemetry (FPS, frame count, detections) | Active |
| `GET` | `/api/detections` | Paginated list of structured vehicle & plate detection events | Active |
| `GET` | `/api/detections/latest` | Most recent vehicle & license plate detection event | Active |
| `GET` | `/api/vehicles` | List of all registered vehicle identities with visit counts & canonical plates | Active |
| `GET` | `/api/vehicles/{id}` | Detailed vehicle record by ID with active status | Active |
| `GET` | `/api/vehicles/{id}/history` | Historical timeline of all visual observations for a vehicle | Active |
| `GET` | `/api/vehicles/{id}/comparison` | Side-by-side evidence: current vs historical vehicle & plate crops | Active |
| `GET` | `/api/identity-events` | Chronological feed of identity match decision events (Rules A–E) | Active |
| `GET` | `/api/identity-events/latest` | Most recent identity match decision event | Active |
| `GET` | `/api/identity-events/{id}` | Single identity observation record by ID | Active |
| `POST` | `/api/demo/scenario/start` | Launch one of 4 controlled demo scenarios | Active |
| `POST` | `/api/demo/scenario/stop` | Gracefully stop active scenario runner | Active |
| `GET` | `/api/demo/scenario/status` | Real-time scenario telemetry (step, event, similarity, crops) | Active |
| `POST` | `/api/demo/reset` | Purge demo records (`is_demo = 1`) without schema alteration | Active |
| `GET` | `/evidence/{filename}` | Direct static HTTP access to saved evidence frames and crops | Active |

---

## 3. Current Database Tables (`vtrace.db`)

1. **`detections`**:
   - Fields: `id`, `camera_id`, `zone`, `timestamp`, `frame_number`, `status`, `vehicle_class`, `vehicle_confidence`, `plate`, `raw_plate`, `plate_confidence`, `ocr_confidence`, `vehicle_bbox`, `plate_bbox`, `vehicle_crop_path`, `plate_crop_path`, `frame_path`, `annotated_frame_path`, `vehicle_id`, `visual_similarity`, `identity_event`, `identity_match_status`, `is_demo`, `created_at`.
2. **`vehicle_identities`**:
   - Fields: `id`, `vehicle_id`, `canonical_plate`, `first_seen`, `last_seen`, `visit_count`, `vehicle_class`, `color`, `embedding_json`, `is_demo`, `created_at`, `updated_at`.
3. **`identity_observations`**:
   - Fields: `id`, `vehicle_identity_id`, `observed_plate`, `plate_confidence`, `ocr_confidence`, `visual_similarity`, `event_type`, `camera_id`, `zone`, `timestamp`, `frame_number`, `vehicle_crop_path`, `plate_crop_path`, `frame_path`, `previous_crop_path`, `is_demo`.

---

## 4. Existing Demo Scenario Mechanism

- Scenarios defined in `backend/demo/scenarios.py`:
  - `NORMAL_REPEAT`: White Sedan $\rightarrow$ White Sedan (`SAME_VEHICLE`, sim $\ge 0.90$)
  - `IDENTITY_MISMATCH`: White Sedan $\rightarrow$ Red Truck (`POSSIBLE_IDENTITY_MISMATCH`, sim $\le 0.35$)
  - `PLATE_SWAP`: White Sedan $\rightarrow$ White Sedan with swapped plate (`POSSIBLE_PLATE_SWAP`, sim $\ge 0.88$)
  - `PLATE_UNREADABLE`: White Sedan $\rightarrow$ White Sedan with blurred plate (`PLATE_UNREADABLE_VEHICLE_MATCH`, sim $\ge 0.88$)
- Managed by `backend/demo/scenario_manager.py` using `VehicleIdentityService.process_vehicle()` with `is_demo=True`.
- Uses deterministic synthesized media in `data/demo/scenarios/`.

---

## 5. Frontend Status

- **Status:** Not present in the repository.
- **Node & npm Available:** Node v24.14.1, npm 11.15.0 installed.
- **Requirement:** Build a dedicated, responsive React + Tailwind CSS Command Center web application served either via Vite dev server or static FastAPI build mount with real-time short-interval polling, 4-camera live grid, KPI cards, vehicle drawer/modals, comparison view, timeline history, registry panel, and demo scenario controls.

---

## 6. Exact Files to be Added and Modified

### A. New Modules to Create:

1. **Vehicle Registry Abstraction (`backend/vehicle_registry/`):**
   - `backend/vehicle_registry/__init__.py`
   - `backend/vehicle_registry/base_registry.py` (Abstract `VehicleRegistry` interface)
   - `backend/vehicle_registry/demo_registry.py` (Local SQLite-backed `DemoVehicleRegistry`)
   - `backend/vehicle_registry/vahan_registry.py` (Interface/stub for future authorized VAHAN API)
   - `backend/vehicle_registry/registry_service.py` (`VehicleRegistryService` abstraction layer & consistency comparison)
   - `backend/vehicle_registry/schemas.py` (Standard registry schema, consistency results)

2. **Site Context & Permits Engine (`backend/site_context/`):**
   - `backend/site_context/__init__.py`
   - `backend/site_context/zones.py` (Camera zone mapping & zone configuration)
   - `backend/site_context/permits.py` (Permit model, queries, status evaluation)
   - `backend/site_context/route_rules.py` (Deterministic transition & travel time anomaly detection)
   - `backend/site_context/context_service.py` (`SiteContextService` unifying permit + route integrity)
   - `backend/site_context/schemas.py` (Permit, zone, route rule, and check response schemas)

3. **Alert Engine & Unified Trust Snapshot (`backend/alerts/`):**
   - `backend/alerts/__init__.py`
   - `backend/alerts/schemas.py` (`AlertItem`, `VehicleTrustSnapshot`, `DashboardSummary`, `LiveObservation`)
   - `backend/alerts/alert_rules.py` (Deterministic human-authored alert templates)
   - `backend/alerts/alert_service.py` (`AlertService` managing alert queue, deduplication, and persistence)

4. **Frontend Command Center (`frontend/`):**
   - Modern React + Tailwind CSS dashboard application featuring:
     - Header banner with connection status (ONLINE/OFFLINE) and DEMO DATA badge
     - KPI summary cards (Active Vehicles, Detections, Identity Warnings, Access Alerts)
     - Live 4-camera CCTV grid (CAM-01 to CAM-04) with latest frame & vehicle status
     - Latest detected vehicle panel with Trust Snapshot & consistency indicators
     - Identity Alert Banner with "VIEW EVIDENCE" and "VIEW HISTORY" modal triggers
     - Side-by-side Evidence Comparison modal (Current vs Historical crops, similarity, decision, rule)
     - Vehicle Timeline History modal
     - Demo Vehicle Registry inspection panel (clearly marked synthetic data)
     - Alert History table with multi-criteria filtering
     - Interactive Demo Control panel with 1-click scenario buttons and Reset Demo

5. **Automated Tests (`tests/test_final_mvp.py`):**
   - 15 comprehensive unit & integration tests covering all new modules (registry lookup, unknown vehicle, consistency match/mismatch, valid/expired permits, unauthorized zone, valid/impossible routes, dashboard summary, alert creation/deduplication, trust snapshot, end-to-end flows).

6. **Documentation & Deliverables (`ARTIFACTS/`):**
   - `ARTIFACTS/final_architecture.md`
   - `ARTIFACTS/final_demo_script.md`
   - `ARTIFACTS/final_test_report.md`
   - `ARTIFACTS/limitations.md`
   - `ARTIFACTS/future_vahan_integration.md`

### B. Existing Files to Modify (Non-Breaking):

1. **`backend/database/database.py` & `backend/database/models.py`:**
   - Add tables: `vehicle_registry`, `permits`, `camera_zones`, `route_rules`, `alerts`.
   - Add database seed methods for demo registry, site permits, camera zones, and route rules.
   - Add query functions for registry, permits, route integrity history, and alerts.
   - Update `reset_demo_data()` to safely clear demo registry sightings, demo alerts, and reset demo status while preserving seed configurations.

2. **`backend/app.py`:**
   - Initialize and wire `VehicleRegistryService`, `SiteContextService`, and `AlertService`.
   - Expose new endpoints:
     - `GET /api/registry/vehicle/{plate}`
     - `POST /api/demo/registry/reset`
     - `GET /api/permits`
     - `GET /api/permits/{plate}`
     - `GET /api/alerts`
     - `GET /api/alerts/{id}`
     - `GET /api/vehicles/{id}/trust-snapshot`
     - `GET /api/dashboard/summary`
     - `GET /api/dashboard/live`
   - Mount frontend static build (or proxy/static serve) so the UI is accessible at `/`.

3. **`backend/demo/scenario_manager.py`:**
   - Update scenario execution to trigger unified trust snapshots and alerts for complete end-to-end demonstration.

4. **`report_generator.py` & `IVACS_VTRACE_Progress_Report.pdf`:**
   - Update to incorporate all 37+ passing tests, new architectural components, and final MVP sign-off.
