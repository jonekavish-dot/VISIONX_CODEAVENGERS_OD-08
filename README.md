# IVACS V-TRACE
### Vehicle Trust, Route & Evidence Engine
**Problem Statement OD-08:** License Plate Detection and Recognition from construction-site CCTV footage.

---

## 👥 Team Members & Roles (CodeAvengers)

| Name | Role | GitHub | Email | Subsystem Responsibility |
| :--- | :--- | :--- | :--- | :--- |
| **Jone Kavish** | **Team Lead** | [`@jonekavish-dot`](https://github.com/jonekavish-dot) | `jonekavish@gmail.com` | **Backend & Team Lead:** FastAPI REST application, identity comparison endpoints, EasyOCR character extraction pipeline, ResNet18 visual fingerprint engine, database schema & isolated demo reset handler, system architecture |
| **K.V. Pranesh** | **Member 1** | [`@kvpranesh`](https://github.com/kvpranesh) | `kvpranesh49@gmail.com` | **Vehicle Detection & Cooldown:** Ultralytics YOLOv8 nano model integration, multi-class vehicle filtering, temporal cooldown deduplication on identity events |
| **Gowshik Gunal** | **Member 2** | [`@gowshikgunal22`](https://github.com/gowshikgunal22) | `gowshikgunal@gmail.com` | **License Plate Localization & Demo Runner:** Bumper ROI localization, morphological gradient filtering, vehicle-to-plate association, 4-scenario demo state machine implementation |
| **Dinesh Balu** | **Member 3** | [`@dineshbalu7f-glitch`](https://github.com/dineshbalu7f-glitch) | `dineshbalu7.f@gmail.com` | **Video, Test Suite & Media Generator:** Video source abstraction (MP4, RTSP, Webcam), offline deterministic scenario media generator, 8-test scenario QA suite, SQLite persistence layer |

---

## 🎯 Architecture Overview

```
VIDEO STREAM / CONTROLLED SCENARIOS
              │
              ▼
   Frame Sampler (Configurable N frames)
              │
              ▼
   YOLOv8 Vehicle Detector (Car, Truck, Bus, Motorcycle)
              │
              ├─────────────────────────────────────────────────┐
              ▼                                                 ▼
   License Plate Detector (Bumper ROI)           ResNet18 Feature Extractor
              │                                  (512-dim Normalized Embedding)
              ▼                                                 │
   EasyOCR Engine (Slot Normalization)                          │
              │                                                 │
              └───────────────────────┬─────────────────────────┘
                                      ▼
                       Vehicle Identity Service
                    (Cosine Similarity & Rules A-E)
                    (5s Temporal Deduplication Cooldown)
                                      │
                                      ▼
                   Structured DetectionEvent & IdentityEvent
                                      │
     ┌────────────────────────────────┴───────────────────┐
     ▼                                                    ▼
SQLite Database (vtrace.db)                     Evidence Store (data/evidence/)
- detections                                    - current_frame.jpg
- vehicle_identities                            - vehicle_crop.jpg
- identity_observations (is_demo flagged)       - plate_crop.jpg
                                                - annotated_frame.jpg
```

---

## 🛡️ AI & Privacy Policy Compliance
* **Zero Generative AI / LLM at Runtime:** Strictly adheres to OD-08 problem statement rules. All vehicle detection, plate localization, OCR character extraction, and visual fingerprinting run natively using classical computer vision (`OpenCV`), lightweight neural networks (`YOLOv8n`, `ResNet18`), and optical character recognition (`EasyOCR`).
* **Honest Detection Policy:** Never claims unverified ground truth (e.g. "stolen" or "cloned"); analytical alerts use precise qualified signals: `POSSIBLE_IDENTITY_MISMATCH` and `MANUAL VERIFICATION REQUIRED`.
* No external API calls to OpenAI, Gemini, Claude, or third-party cloud LLMs.

---

## 🚦 Controlled Demo Scenarios

| Scenario ID | Step 1 (Baseline) | Step 2 (Trigger) | Decision Emitted | Expected Metric |
| :--- | :--- | :--- | :--- | :--- |
| `NORMAL_REPEAT` | White Sedan (`MH12DE1433`) | White Sedan (`MH12DE1433`) | `SAME_VEHICLE` | Cosine similarity &ge; 0.90 |
| `IDENTITY_MISMATCH` | White Sedan (`MH12DE1433`) | Red Truck (`MH12DE1433`) | `POSSIBLE_IDENTITY_MISMATCH` | Cosine similarity &le; 0.35 |
| `PLATE_SWAP` | White Sedan (`MH12DE1433`) | White Sedan (`KA01AB1234`) | `POSSIBLE_PLATE_SWAP` | Cosine similarity &ge; 0.88 |
| `PLATE_UNREADABLE` | White Sedan (`MH12DE1433`) | White Sedan (`NO_PLATE`) | `PLATE_UNREADABLE_VEHICLE_MATCH` | Cosine similarity &ge; 0.88 |

---

## 🚀 Quick Start

### 1. Installation
```bash
pip install opencv-python ultralytics easyocr fastapi uvicorn reportlab pytest torchvision torch
```

### 2. Run Automated Tests (All 22 Unit, Integration & Scenario Tests)
```bash
python -m pytest tests/ -v
```

### 3. Generate Scenario Media
```bash
python scripts/setup_demo_media.py
```

### 4. Start the Backend Server
Run using the runner script:
```bash
python run_server.py
```
Or via python module syntax:
```bash
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```
Interactive API documentation will be available at: `http://localhost:8000/docs`

### 5. Run Live Verification
```bash
python verify_identity_mismatch_live.py
```

---

## 📡 REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health, active device (CPU/CUDA), and model status |
| `GET` | `/api/cameras` | List configured construction site CCTV cameras (CAM-01 to CAM-04) |
| `POST` | `/api/demo/scenario/start` | Launch one of 4 controlled scenarios (`NORMAL_REPEAT`, `IDENTITY_MISMATCH`, etc.) |
| `POST` | `/api/demo/scenario/stop` | Gracefully stop active scenario runner |
| `GET` | `/api/demo/scenario/status` | Real-time scenario state: active scenario, step index, decision, similarity |
| `POST` | `/api/demo/reset` | Safe purge of demo records (`is_demo = 1`) strictly preserving production schemas |
| `GET` | `/api/vehicles/{vehicle_id}/comparison` | Side-by-side evidence: current vehicle/plate vs historical vehicle/plate, similarity, alert text |
| `GET` | `/api/identity-events/{id}` | Historical identity observation by ID with evidence paths and similarity metrics |
| `GET` | `/api/detections` | Paginated list of all stored detection events from SQLite |
| `GET` | `/api/detections/latest` | Most recent vehicle & license plate detection event |
| `GET` | `/api/vehicles` | List of all registered vehicle identities with visit counts & canonical plates |
| `GET` | `/api/vehicles/{vehicle_id}` | Detailed vehicle record by ID with active status and first/last seen timestamps |
| `GET` | `/api/vehicles/{vehicle_id}/history` | Historical timeline of all visual observations and sightings for a vehicle |
| `GET` | `/api/identity-events` | Feed of identity match events with decision rules (Rules A-E) and similarity scores |
| `GET` | `/api/identity-events/latest` | Most recent identity match decision event |
| `GET` | `/evidence/{filename}` | Direct static HTTP access to saved evidence frames and crops |

---

## 📄 Progress Report
A live, continuously updated PDF progress report is saved directly in the project root:
**`IVACS_VTRACE_Progress_Report.pdf`**
You can update it at any time by executing:
```bash
python report_generator.py
```
