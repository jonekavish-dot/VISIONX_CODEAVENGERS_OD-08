# IVACS V-TRACE
### Vehicle Trust, Route & Evidence Engine
**Problem Statement OD-08:** License Plate Detection and Recognition from Construction-Site CCTV Footage  
**Runtime AI Policy:** **Strict Zero LLM / Zero Generative AI at Runtime** (Native Computer Vision, Deep Visual Embeddings & Deterministic Trust Pipeline)

---

## 👥 Team Members & Roles (CodeAvengers)

| Name | Role | GitHub | Email | Subsystem Responsibility |
| :--- | :--- | :--- | :--- | :--- |
| **Jone Kavish** | **Team Lead** | [`@jonekavish-dot`](https://github.com/jonekavish-dot) | `jonekavish@gmail.com` | **Backend & Team Lead, OCR, React Command Center:** Overall system architecture, FastAPI web service (29 endpoints), React Command Center UI, EasyOCR character extraction pipeline, ResNet18 visual fingerprint engine, database schema & isolated demo reset handler, report generation, Git management. |
| **K.V. Pranesh** | **Member 1** | [`@kvpranesh`](https://github.com/kvpranesh) | `kvpranesh49@gmail.com` | **Security Alert Engine & Deduplication:** Deterministic alert rule templates, 10s temporal cooldown deduplication, explainable `VehicleTrustSnapshot` synthesis, YOLOv8 nano vehicle detector integration, 15-test final MVP QA suite. |
| **Gowshik Gunal** | **Member 2** | [`@gowshikgunal22`](https://github.com/gowshikgunal22) | `gowshikgunal@gmail.com` | **Vehicle Registry & Plate Localization:** Vehicle registry abstraction layer (`DemoVehicleRegistry` SQLite implementation + `VahanVehicleRegistry` government stub), registry attribute consistency check, bumper-ROI plate localization, 4-scenario demo state machine. |
| **Dinesh Balu** | **Member 3** | [`@dineshbalu7f-glitch`](https://github.com/dineshbalu7f-glitch) | `dineshbalu7.f@gmail.com` | **Site Context, Route Integrity & Media:** Construction site permit manager, camera zone topology (CAM-01 to CAM-04), route integrity checker (impossible transitions & speed violations), offline scenario media generator, SQLite persistence layer. |

---

## 🎯 Architecture Overview

```
                      +-----------------------------------------------+
                      |          Construction-Site CCTV Feeds         |
                      |   CAM-01 (Entry) | CAM-02 (Batching Plant)    |
                      |   CAM-03 (Loading Area) | CAM-04 (Exit Gate)  |
                      +-----------------------------------------------+
                                             |
                                             v
                      +-----------------------------------------------+
                      |      Video Ingestion Layer (MP4/RTSP/Webcam)  |
                      |      Configurable Frame Stride & Decimation   |
                      +-----------------------------------------------+
                                             |
                                             v
                      +-----------------------------------------------+
                      |       Vehicle Detection (YOLOv8n - PyTorch)   |
                      |       Classes: car, truck, bus, motorcycle    |
                      +-----------------------------------------------+
                                             |
                                             v
                      +-----------------------------------------------+
                      |    Bumper-ROI Plate Localization (OpenCV)     |
                      |   Morphological Gradients + Geometric Filters |
                      +-----------------------------------------------+
                                             |
                                             v
                      +-----------------------------------------------+
                      |       Plate Text Recognition (EasyOCR)        |
                      |    IND Blue Strip Cropping + Slot Format      |
                      +-----------------------------------------------+
                                             |
                                             v
                      +-----------------------------------------------+
                      |   ResNet18 Deep Visual Fingerprint (512-D)    |
                      |      L2-Normalized Embedding Extraction       |
                      +-----------------------------------------------+
                                             |
                                             v
                      +-----------------------------------------------+
                      |   Deterministic Identity Decision Engine      |
                      |        Cosine Similarity & Rules A - E        |
                      +-----------------------------------------------+
                                             |
                    +------------------------+------------------------+
                    |                                                 |
                    v                                                 v
+-----------------------------------+             +-----------------------------------+
|     Vehicle Registry Service      |             |    Site Context & Route Engine    |
| (Demo Registry / VAHAN Connector) |             |  (Permit Validation & Transits)   |
+-----------------------------------+             +-----------------------------------+
                    \                                                 /
                     \                                               /
                      +---------------------------------------------+
                      |       Security Alert Engine & Deduplication |
                      |       (10s Cooldown, Rules-Based Alerts)    |
                      +---------------------------------------------+
                                             |
                                             v
                      +---------------------------------------------+
                      |  Unified SQLite Persistence (vtrace.db)     |
                      |  Multi-Scale Evidence Store (data/evidence/)|
                      +---------------------------------------------+
                                             |
                                             v
                      +---------------------------------------------+
                      |  FastAPI Web Service (29 Endpoints)         |
                      +---------------------------------------------+
                                             |
                                             v
                      +---------------------------------------------+
                      |   React / Tailwind Command Center Dashboard |
                      | (4-CCTV Grid, KPI Bar, Alert Log, Scenarios)|
                      +---------------------------------------------+
```

---

## 🛡️ AI & Privacy Policy Compliance
* **Zero Generative AI / LLM at Runtime:** Strictly adheres to OD-08 problem statement rules. All vehicle detection, plate localization, OCR character extraction, and visual fingerprinting run natively using classical computer vision (`OpenCV`), lightweight neural networks (`YOLOv8n`, `ResNet18`), and optical character recognition (`EasyOCR`).
* **Honest Detection Policy:** Never claims unverified ground truth (e.g. "stolen" or "cloned"); analytical alerts use precise qualified signals: `POSSIBLE_IDENTITY_MISMATCH` and `MANUAL VERIFICATION REQUIRED`.
* **Zero External Cloud Calls:** Operates 100% offline at the edge without third-party API dependencies or data leakage.

---

## 🚦 Deterministic Decision Rules & Scenarios

| Rule Code | Plate Observed | Visual Match ($\ge 0.85$) | Decision Output | Risk Level | Action Triggered |
|---|---|---|---|---|---|
| **Rule A** | Known Plate | **Yes** | `SAME_VEHICLE` | **LOW** | Consistent observation; update centroid |
| **Rule B** | Known Plate | **No** | `POSSIBLE_IDENTITY_MISMATCH` | **CRITICAL** | Security alert; prompt side-by-side evidence audit |
| **Rule C** | Different Plate | **Yes** | `POSSIBLE_PLATE_SWAP` | **HIGH** | Security alert; vehicle re-identified under false tag |
| **Rule D** | Unreadable | **Yes** | `PLATE_UNREADABLE_VEHICLE_MATCH` | **MEDIUM** | Visual tracking continuity preserved |
| **Rule E** | First Sighting | N/A | `NEW_VEHICLE` | **INFO** | Register new persistent vehicle identity |

### Controlled Hackathon Demo Scenarios

| Scenario ID | Step 1 (Baseline) | Step 2 (Trigger) | Decision Emitted | Expected Metric |
| :--- | :--- | :--- | :--- | :--- |
| `NORMAL_REPEAT` | Tata Starbus (`MH12DE1433`) | Tata Starbus (`MH12DE1433`) | `SAME_VEHICLE` | Cosine similarity &ge; 0.90 |
| `IDENTITY_MISMATCH` | Tata Starbus (`MH12DE1433`) | Tipper Truck (`MH12DE1433`) | `POSSIBLE_IDENTITY_MISMATCH` | Cosine similarity &le; 0.35 |
| `PLATE_SWAP` | Tata Starbus (`MH12DE1433`) | Tata Starbus (`KA01AB1234`) | `POSSIBLE_PLATE_SWAP` | Cosine similarity &ge; 0.88 |
| `PLATE_UNREADABLE` | Tata Starbus (`MH12DE1433`) | Tata Starbus (`NO_PLATE`) | `PLATE_UNREADABLE_VEHICLE_MATCH` | Cosine similarity &ge; 0.88 |

---

## 📡 Complete REST API Taxonomy (29 Endpoints)

| Category | Method | Endpoint | Description |
| :--- | :--- | :--- | :--- |
| **System** | `GET` | `/api/health` | Service health, active compute device (CPU/CUDA), and model status |
| **Dashboard** | `GET` | `/api/dashboard/summary` | Aggregate fleet metrics: active alerts, total vehicles, trust index |
| **Dashboard** | `GET` | `/api/dashboard/live` | Real-time live status for 4 camera cards (plate, speed, permit, route) |
| **Cameras** | `GET` | `/api/cameras` | List configured construction site CCTV cameras (CAM-01 to CAM-04) |
| **Cameras** | `GET` | `/api/cameras/{id}/stream` | MJPEG streaming video feed for live monitoring grid |
| **Detections** | `POST` | `/api/process-video` | Ingests video file or stream URL through detection and OCR pipeline |
| **Detections** | `GET` | `/api/detections` | Paginated list of all stored detection events from SQLite |
| **Detections** | `GET` | `/api/detections/latest` | Most recent vehicle & license plate detection event |
| **Detections** | `GET` | `/api/detections/{id}` | Single detection event detail with evidence crops |
| **Identity** | `GET` | `/api/vehicles` | List of all registered vehicle identities with visit counts & canonical plates |
| **Identity** | `GET` | `/api/vehicles/{id}` | Detailed vehicle record by ID with active status and first/last seen |
| **Identity** | `GET` | `/api/vehicles/{id}/history` | Historical timeline of all visual observations and sightings |
| **Identity** | `GET` | `/api/vehicles/{id}/comparison` | Side-by-side evidence: current vehicle/plate vs historical reference |
| **Identity** | `GET` | `/api/vehicles/{id}/trust-snapshot` | Multi-factor vehicle trust calculation, visual match, permit & route checks |
| **Identity** | `GET` | `/api/identity-events` | Feed of identity match events with decision rules (A-E) and similarities |
| **Identity** | `GET` | `/api/identity-events/latest` | Most recent identity match decision event |
| **Identity** | `GET` | `/api/identity-events/{id}` | Historical identity observation by ID with evidence paths and metrics |
| **Alerts** | `GET` | `/api/alerts` | Paginated security alert feed filtered by severity, camera, or status |
| **Alerts** | `GET` | `/api/alerts/{id}` | Single alert detail breakdown with JSON payload |
| **Alerts** | `POST` | `/api/alerts/{id}/dismiss` | Operator alert acknowledgement and dismissal handler |
| **Registry** | `GET` | `/api/registry/vehicle/{plate}` | Vehicle registration query (RTO/VAHAN mock structure) |
| **Registry** | `POST` | `/api/demo/registry/reset` | Reset demo registry table to factory state |
| **Permits** | `GET` | `/api/permits` | Active and historical construction site access permits |
| **Permits** | `GET` | `/api/permits/{plate}` | Permits associated with a specific vehicle plate |
| **Site** | `GET` | `/api/site/zones` | Camera-to-zone spatial topological mapping |
| **Site** | `GET` | `/api/site/routes` | Directed graph of permitted transitions and traversal durations |
| **Scenarios** | `POST` | `/api/demo/scenario/start` | Launch one of 4 controlled scenarios (`NORMAL_REPEAT`, `IDENTITY_MISMATCH`, etc.) |
| **Scenarios** | `POST` | `/api/demo/scenario/stop` | Gracefully stop active scenario runner |
| **Scenarios** | `GET` | `/api/demo/scenario/status` | Real-time scenario state: active scenario, step index, decision, similarity |
| **Scenarios** | `POST` | `/api/demo/reset` | Safe purge of demo records (`is_demo = 1`) strictly preserving production schemas |
| **Live YouTube** | `POST` | `/api/live/youtube/start` | Connect & ingest public YouTube livestream URL via yt-dlp |
| **Live YouTube** | `POST` | `/api/live/youtube/stop` | Gracefully terminate active YouTube livestream ingestion |
| **Live YouTube** | `GET` | `/api/live/youtube/status` | Real-time status (OFFLINE, CONNECTING, CONNECTED, RECONNECTING) & metrics |
| **Live YouTube** | `GET` | `/api/live/youtube/frame` | Streaming/snapshot JPEG of latest processed live internet frame |
| **Live YouTube** | `GET` | `/api/live/youtube/latest` | Latest vehicle detection event from active public YouTube livestream |
| **Media** | `GET` | `/api/media` | Universal local evidence image streaming endpoint (handles absolute & relative paths) |
| **Media** | `GET` | `/evidence/{filename}` | Direct static HTTP access to saved evidence frames and crops |

---

## 🌐 Public Internet Camera & YouTube Live Ingestion

IVACS V-TRACE supports direct ingestion of live public internet cameras and YouTube livestreams without caching or saving whole video files:

* **Architecture:** `YouTube URL` $\to$ `yt-dlp stream extraction` $\to$ `OpenCV live HLS stream` $\to$ `FrameProcessor` (YOLOv8 + EasyOCR + ResNet18)
* **Labeling:** Clearly segregated in the UI and database as **`PUBLIC INTERNET STREAM`** (distinct from construction site CCTV).
* **Live Stream Verification:**
  ```bash
  python scripts/verify_youtube_live.py
  ```
  *(Verified with Coimbatore Avinashi Road public traffic camera: `https://www.youtube.com/watch?v=tmMrGbBOi1U`)*

---

## 🧪 Automated QA Suite (42/42 Passing - 100%)

The complete test suite verifies the end-to-end computer vision pipeline, deep visual embeddings, deterministic rules, registry consistency checks, site permits, route anomalies, alert deduplication, and YouTube live ingestion.

```bash
python -m pytest tests/ -v
```

```
====================== 42 passed in 29.49s =======================
tests/test_final_mvp.py (15/15 PASS)
tests/test_demo_scenarios.py (8/8 PASS)
tests/test_identity.py (7/7 PASS)
tests/test_vtrace.py (7/7 PASS)
tests/test_youtube_source.py (5/5 PASS)
```

---

## 🚀 Quick Start Guide

### 1. Installation
```bash
pip install opencv-python ultralytics easyocr fastapi uvicorn reportlab pytest torchvision torch yt-dlp
```

### 2. Build Frontend (React Command Center)
```bash
cd frontend
npm install
npm run build
cd ..
```
*(The pre-built React application is automatically served by FastAPI at `http://localhost:8000/`)*

### 3. Generate Scenario Media
```bash
python scripts/setup_demo_media.py
```

### 4. Start the Unified Server
```bash
python run_server.py
```
* **Command Center Dashboard:** Open `http://localhost:8000` in your web browser.
* **Interactive API Documentation:** Open `http://localhost:8000/docs` (Swagger UI).

### 5. Run Live Verification
```bash
python verify_identity_mismatch_live.py
```

---

## 📄 Project Documentation & Reports

* **Audit Progress Report (PDF):** `IVACS_VTRACE_Progress_Report.pdf` (Workspace root)
* **Final Architecture Specification:** [`ARTIFACTS/final_architecture.md`](ARTIFACTS/final_architecture.md)
* **90-Second Evaluator Demo Script:** [`ARTIFACTS/final_demo_script.md`](ARTIFACTS/final_demo_script.md)
* **Complete QA Test Verification Report:** [`ARTIFACTS/final_test_report.md`](ARTIFACTS/final_test_report.md)
* **Operational Limitations & Edge Cases:** [`ARTIFACTS/limitations.md`](ARTIFACTS/limitations.md)
* **Future Government VAHAN Integration:** [`ARTIFACTS/future_vahan_integration.md`](ARTIFACTS/future_vahan_integration.md)

To regenerate the PDF report at any time:
```bash
python report_generator.py
```
