# IVACS V-TRACE: Current State Assessment

## 1. Executive Summary
This document provides the baseline inspection of the repository located at `d:\VISIONX` prior to implementation of the **IVACS V-TRACE (Vehicle Trust, Route & Evidence Engine)** foundation for Problem Statement **OD-08 — License Plate Detection and Recognition from construction-site CCTV footage**.

---

## 2. Files Found in Repository

| Filename | Size (Bytes) | Description / Type |
| :--- | :--- | :--- |
| `IVACS_6Hour_Hackathon_Strategy.md` | 17,496 | Strategy and timeline plan for a 6-hour hackathon execution |
| `IVACS_Execution_Plan.md` | 16,528 | Enterprise roadmap and phase breakdown document |
| `IVACS_Hackathon_Quick_Reference.txt` | 21,178 | Quick reference guide with code snippets for YOLOv8 and EasyOCR |
| `IVACS_SRS_Presentation.pptx` | 55,660 | Presentation deck for IVACS system requirements and problem statement |
| `IVACS_Technical_Implementation.md` | 26,367 | Code architecture guide with sample snippets for detection engine, OCR, and schemas |

---

## 3. Analysis of Current Repository State

* **Current Backend:**
  No executable backend application code exists in the repository yet. Only architectural documentation and markdown code examples are present.
  FastAPI, Uvicorn, Pydantic, and SQLite are already installed in the Python 3.14 environment.

* **Current Frontend:**
  No frontend code or React application exists in the repository.

* **Current ML Code:**
  No active Python ML pipeline or model weights currently exist in the directory. The Markdown documents outline reference snippets for `ultralytics` YOLO and `easyocr`.

* **Current Dependencies:**
  Python 3.14.3 is active with FastAPI, Uvicorn, ReportLab, Pydantic, Requests, PyTest, Pillow, and Scipy installed. The computer vision libraries (`opencv-python`, `ultralytics`, `easyocr`, `torch`, `torchvision`) are currently being installed.

* **Existing Database:**
  No database file or schema has been instantiated yet. SQLite3 is built into Python.

* **Existing Routes:**
  No routes implemented yet.

* **Existing Components:**
  None implemented yet.

* **Reusable Code:**
  - Code snippets inside `IVACS_Technical_Implementation.md` (e.g. YOLO box extraction logic, EasyOCR post-processing patterns for Indian license plate formats).
  - Quick reference detection snippet from `IVACS_6Hour_Hackathon_Strategy.md`.

* **Problems Found:**
  1. Complete absence of actual runnable source code in the repository.
  2. Missing test videos in `data/demo/`.
  3. Missing structured database and API.
  4. The documentation contains over-engineered enterprise items (Docker, Redis, K8s, microservices) which contradict the 5-hour hackathon demo-first constraint.

---

## 4. Changes Required for V-TRACE Target Architecture

We will implement a clean, demo-first, modular architecture following the exact target specifications:

```
VISIONX/
├── backend/
│   ├── app.py                     # FastAPI application entrypoint & API endpoints
│   ├── config.py                  # System & Camera configurations (CAM-01 to CAM-04)
│   ├── video/
│   │   ├── base_source.py         # Abstract VideoSource interface
│   │   ├── mp4_source.py          # MP4 video reader with sampling & frame generator
│   │   ├── rtsp_source.py         # RTSP stream handler stub
│   │   └── webcam_source.py       # Webcam source handler
│   ├── detection/
│   │   ├── vehicle_detector.py    # YOLO nano/small vehicle detector (car, truck, bus, motorcycle)
│   │   └── plate_detector.py      # License plate detector & vehicle ROI association
│   ├── ocr/
│   │   └── plate_ocr.py           # EasyOCR engine preserving raw_text & normalized_text
│   ├── services/
│   │   └── frame_processor.py     # End-to-end pipeline: Frame -> Detection -> OCR -> Event
│   ├── database/
│   │   ├── database.py            # SQLite connection and session management
│   │   └── models.py              # Detections table model
│   └── schemas/
│       └── detection.py           # Pydantic schemas for DetectionEvent and API responses
├── data/
│   ├── demo/                      # Demo MP4 video (construction_site.mp4)
│   └── evidence/                  # Evidence crops (current_frame, vehicle_crop, plate_crop)
├── tests/
│   └── test_vtrace.py             # Comprehensive test suite covering all 7 mandatory areas
├── ARTIFACTS/
│   └── current_state.md           # Baseline state report
└── IVACS_VTRACE_Progress_Report.pdf # Continuous PDF progress report updated at each milestone
```

---

## 5. Execution Sequence

1. Complete CV/ML dependency installation (`opencv-python`, `ultralytics`, `torch`, `easyocr`).
2. Implement PDF Report Generator (`report_generator.py`) to maintain `IVACS_VTRACE_Progress_Report.pdf` at every step.
3. Build `backend/config.py` and `backend/schemas/detection.py`.
4. Implement `backend/video/` (base_source, mp4_source, rtsp_source, webcam_source).
5. Implement `backend/database/` (SQLite models and database operations).
6. Implement `backend/detection/` (vehicle_detector and plate_detector) and `backend/ocr/` (plate_ocr).
7. Implement `backend/services/frame_processor.py` with visual overlay & evidence storage.
8. Create `backend/app.py` with endpoints (`/api/health`, `/api/detections`, `/api/detections/latest`, `/api/demo/start`, `/api/demo/stop`, `/api/demo/status`).
9. Generate or provide demo video in `data/demo/construction_site.mp4`.
10. Implement comprehensive unit/integration tests in `tests/test_vtrace.py`.
11. Run tests and execute live demo pipeline, verifying database entries, evidence files, and API outputs.
12. Update the PDF report with final status table.
