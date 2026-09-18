# IVACS V-TRACE
### Vehicle Trust, Route & Evidence Engine
**Problem Statement OD-08:** License Plate Detection and Recognition from construction-site CCTV footage.

---

## 👥 Team Members & Roles (CodeAvengers)

| Name | Role | GitHub | Email | Subsystem Responsibility |
| :--- | :--- | :--- | :--- | :--- |
| **Jone Kavish** | **Team Lead** | [`@jonekavish-dot`](https://github.com/jonekavish-dot) | `jonekavish@gmail.com` | **Backend & Team Lead:** FastAPI application, REST endpoints, EasyOCR character extraction pipeline, frame orchestrator, system architecture |
| **K.V. Pranesh** | **Member 1** | [`@kvpranesh`](https://github.com/kvpranesh) | `kvpranesh49@gmail.com` | **Vehicle Detection:** Ultralytics YOLOv8 nano/small model integration, multi-class vehicle classification (car, truck, bus, motorcycle), confidence tuning |
| **Gowshik Gunal** | **Member 2** | [`@gowshikgunal22`](https://github.com/gowshikgunal22) | `gowshikgunal@gmail.com` | **License Plate Localization:** Bumper ROI localization, morphological gradient filtering, vehicle-to-plate bounding box association |
| **Dinesh Balu** | **Member 3** | [`@dineshbalu7f-glitch`](https://github.com/dineshbalu7f-glitch) | `dineshbalu7.f@gmail.com` | **Video & Persistence:** Video source abstraction (MP4, RTSP, Webcam), configurable frame sampling, evidence crop storage, SQLite database |

---

## 🎯 Architecture Overview

```
VIDEO STREAM (MP4 / RTSP / Webcam)
              │
              ▼
   Frame Sampler (Configurable N frames)
              │
              ▼
   YOLOv8 Vehicle Detector (Car, Truck, Bus, Motorcycle)
              │
              ▼
   License Plate Detector (Bumper ROI & Morphological Analysis)
              │
              ▼
   Plate Crop & CLAHE Preprocessing
              │
              ▼
   EasyOCR Engine (Raw OCR text + Disciplined Plate Normalization)
              │
              ▼
   Structured DetectionEvent (Vehicle + Plate Association)
              │
     ┌────────┴───────────────────────────┐
     ▼                                    ▼
SQLite Database (vtrace.db)       Evidence Store (data/evidence/)
                                  - current_frame.jpg
                                  - vehicle_crop.jpg
                                  - plate_crop.jpg
                                  - annotated_frame.jpg
```

---

## 🛡️ AI & Privacy Policy Compliance
* **Zero Generative AI / LLM at Runtime:** Strictly adheres to OD-08 problem statement rules. All vehicle detection, plate localization, and OCR character extraction run natively using classical computer vision (`OpenCV`), lightweight neural network (`YOLOv8`), and optical character recognition (`EasyOCR`).
* No external API calls to OpenAI, Gemini, Claude, or third-party cloud LLMs.

---

## 🚀 Quick Start

### 1. Installation
```bash
pip install opencv-python ultralytics easyocr fastapi uvicorn reportlab pytest
```

### 2. Run Automated Tests (All 7 Core Areas)
```bash
python -m pytest tests/test_vtrace.py -v
```

### 3. Generate CCTV Demo Video
```bash
python create_demo_video.py
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
python verify_demo.py
```

---

## 📡 REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health, active device (CPU/CUDA), and model status |
| `GET` | `/api/cameras` | List configured construction site CCTV cameras (CAM-01 to CAM-04) |
| `POST` | `/api/demo/start` | Launch non-blocking background video processing on demo CCTV stream |
| `POST` | `/api/demo/stop` | Gracefully stop active background video processing |
| `GET` | `/api/demo/status` | Real-time demo metrics: current frame, total frames, FPS, detection count |
| `GET` | `/api/detections` | Paginated list of all stored detection events from SQLite |
| `GET` | `/api/detections/latest` | Most recent vehicle & license plate detection event |
| `GET` | `/evidence/{filename}` | Direct static HTTP access to saved evidence frames and crops |

---

## 📄 Progress Report
A live, continuously updated PDF progress report is saved directly in the project root:
**`IVACS_VTRACE_Progress_Report.pdf`**
You can update it at any time by executing:
```bash
python report_generator.py
```
