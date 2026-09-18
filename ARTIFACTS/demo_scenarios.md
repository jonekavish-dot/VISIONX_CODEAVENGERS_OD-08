# IVACS V-TRACE: Controlled Demo Scenarios Specification

**Document:** `ARTIFACTS/demo_scenarios.md`  
**Problem Statement:** OD-08 — License Plate Detection, Recognition & Vehicle Identity Engine  
**Runtime AI Policy:** Strict Zero Generative AI / Zero LLM. 100% Native Edge Computer Vision (YOLOv8n, EasyOCR, ResNet18, OpenCV).  

---

## Overview

The IVACS V-TRACE Demo Scenario Engine provides deterministic, repeatable, and offline test executions for judges and evaluators to observe the core analytical capabilities of the Vehicle Visual Fingerprint Engine without waiting for live CCTV streams.

All visual similarity metrics and identity decisions are calculated live by the real ResNet18 feature extractor model and deterministic decision rules (Rules A through E).

---

## Scenario Catalog

### Scenario 1: NORMAL_REPEAT
* **Concept:** Verified Identity Baseline Repeat
* **Operational Meaning:** Same registered license plate observed on an identical physical vehicle appearance.
* **Input:**
  - Step 1: Red Indian Bus crop + Plate `TN01AB1234`
  - Step 2: Red Indian Bus crop (slight illumination variance) + Plate `TN01AB1234`
* **Expected Detection:** Vehicle Class: `bus` (Conf: ~0.95), Plate: `TN01AB1234` (OCR Conf: ~0.94)
* **Real Computed Visual Similarity:** $\ge 0.85$ (Actual: `~0.999`)
* **Expected Identity Result:** `SAME_VEHICLE` (Rule A)
* **Manual Review Required:** `False`
* **Evidence Produced:**
  - Baseline vehicle crop + plate crop
  - Current vehicle crop + plate crop
  - Verified Identity event logged to SQLite `identity_observations`

---

### Scenario 2: IDENTITY_MISMATCH (Primary Innovation)
* **Concept:** Possible Plate Cloning / Vehicle Swap Anomaly
* **Operational Meaning:** An observed vehicle carries a license plate that was previously associated with a completely different physical vehicle appearance.
* **Input:**
  - Step 1 (Historical Baseline): Red Indian Bus crop + Plate `TN01AB1234`
  - Step 2 (Current Vehicle): Heavy White/Silver Construction Tipper Truck + Plate `TN01AB1234`
* **Expected Detection:** Current Vehicle Class: `truck` (Conf: ~0.95), Plate: `TN01AB1234` (OCR Conf: ~0.93)
* **Real Computed Visual Similarity:** $< 0.85$ (Actual: `~0.700`)
* **Expected Identity Result:** `POSSIBLE_IDENTITY_MISMATCH` (Rule B)
* **Manual Review Required:** `True`
* **Alert Title:** `"POSSIBLE PLATE–VEHICLE IDENTITY MISMATCH"`
* **Alert Message:** `"Observed plate TN01AB1234 is associated with a vehicle appearance that differs from the historical vehicle profile."`
* **Evidence Produced:**
  - Side-by-side comparative evidence packet:
    - `current_vehicle_image` (White Tipper Truck)
    - `historical_vehicle_image` (Red Bus)
    - `current_plate_image` (`TN01AB1234`)
    - `historical_plate_image` (`TN01AB1234`)
  - Full metadata packet with visual similarity score `0.700` and `requires_manual_review = true`

---

### Scenario 3: PLATE_SWAP
* **Concept:** Same Vehicle Bearing an Unexpected Plate
* **Operational Meaning:** A vehicle matching a known physical vehicle appearance arrives displaying a different license plate.
* **Input:**
  - Step 1 (Historical Baseline): Red Indian Bus crop + Plate `TN01AB1234`
  - Step 2 (Current Vehicle): Same Red Indian Bus crop + Plate `KA05CD5678`
* **Expected Detection:** Vehicle Class: `bus` (Conf: ~0.95), Plate: `KA05CD5678` (OCR Conf: ~0.92)
* **Real Computed Visual Similarity:** $\ge 0.85$ (Actual: `~0.999`)
* **Expected Identity Result:** `POSSIBLE_PLATE_SWAP` (Rule C)
* **Manual Review Required:** `True`
* **Alert Title:** `"POSSIBLE PLATE SWAP"`
* **Alert Message:** `"Observed vehicle appearance matches a historical vehicle associated with another plate, but carries plate KA05CD5678."`
* **Evidence Produced:**
  - Historical bus crop with plate `TN01AB1234`
  - Current bus crop with plate `KA05CD5678`
  - Analytical anomaly record emitted to `/api/identity-events`

---

### Scenario 4: PLATE_UNREADABLE
* **Concept:** Tracking Continuity Across OCR Failure
* **Operational Meaning:** Vehicle license plate is obscured by mud, glare, or motion blur, but the visual fingerprint matches a known identity in the database.
* **Input:**
  - Step 1 (Historical Baseline): Red Indian Bus crop + Plate `TN01AB1234`
  - Step 2 (Current Vehicle): Same Red Indian Bus crop + Obscured/Blurred Plate (`None`)
* **Expected Detection:** Vehicle Class: `bus` (Conf: ~0.95), Plate: `None` (OCR Conf: `0.0`)
* **Real Computed Visual Similarity:** $\ge 0.85$ (Actual: `~0.999`)
* **Expected Identity Result:** `PLATE_UNREADABLE_VEHICLE_MATCH` (Rule D)
* **Manual Review Required:** `False`
* **Alert Title:** `"PLATE UNREADABLE — VEHICLE CONTINUITY FOUND"`
* **Alert Message:** `"Observed license plate is unreadable or obscured, but vehicle visual appearance strongly matches historical profile."`
* **Evidence Produced:**
  - Vehicle visual tracking continuity maintained without losing track of the physical asset.

---

## Verification & API Access Reference

| Scenario | API Trigger | Verification Endpoint |
| :--- | :--- | :--- |
| `NORMAL_REPEAT` | `POST /api/demo/scenario/start` (`{"scenario": "NORMAL_REPEAT"}`) | `GET /api/vehicles/{id}/comparison` |
| `IDENTITY_MISMATCH` | `POST /api/demo/scenario/start` (`{"scenario": "IDENTITY_MISMATCH"}`) | `GET /api/vehicles/{id}/comparison` |
| `PLATE_SWAP` | `POST /api/demo/scenario/start` (`{"scenario": "PLATE_SWAP"}`) | `GET /api/vehicles/{id}/comparison` |
| `PLATE_UNREADABLE` | `POST /api/demo/scenario/start` (`{"scenario": "PLATE_UNREADABLE"}`) | `GET /api/identity-events/latest` |
| Demo Reset | `POST /api/demo/reset` | `GET /api/demo/scenario/status` |
