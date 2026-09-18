# IVACS V-TRACE: Vehicle Visual Fingerprint Engine Report

## 1. Executive Summary
This document provides the technical report for the **Vehicle Visual Fingerprint Engine**, implemented as the second phase of **IVACS V-TRACE (Vehicle Trust, Route & Evidence Engine)** for Problem Statement **OD-08**.

The engine computes a persistent visual appearance representation of physical vehicles to verify identity consistency, assisting in the detection of plate swapping, plate cloning, identity mismatch, and continuity during OCR dropouts.

---

## 2. Architecture & File Inventory

### Files Added:
* `backend/vehicle_identity/__init__.py`: Package entrypoint exporting identity modules.
* `backend/vehicle_identity/feature_extractor.py`: ResNet18 feature extraction backbone with L2-normalized 512-dim embedding.
* `backend/vehicle_identity/similarity.py`: Normalized cosine similarity engine.
* `backend/vehicle_identity/identity_rules.py`: Deterministic implementation of decision Rules A through E.
* `backend/vehicle_identity/identity_service.py`: Vehicle identity manager, matching service, and observation logger.
* `backend/vehicle_identity/schemas.py`: Pydantic models for `VehicleIdentity`, `IdentityObservation`, `IdentityEventType`, and match results.
* `tests/test_identity.py`: Deterministic test suite covering all 5 core identity lifecycle scenarios.
* `verify_identity_api.py`: Comprehensive integration test for new identity endpoints.

### Files Modified:
* `backend/config.py`: Added demo calibration thresholds (`IDENTITY_HIGH_THRESHOLD = 0.85`, `IDENTITY_LOW_THRESHOLD = 0.60`).
* `backend/database/models.py`: Added `vehicle_identities` and `identity_observations` table schemas.
* `backend/database/database.py`: Added non-breaking schema migrations, identity persistence functions, and enriched detection fields.
* `backend/schemas/detection.py`: Extended `DetectionEvent` with `vehicle_id`, `visual_similarity`, `identity_event`, and `identity_match_status`.
* `backend/services/frame_processor.py`: Integrated `identity_service` into the frame pipeline following vehicle & plate detection.
* `backend/app.py`: Added `/api/vehicles`, `/api/vehicles/{vehicle_id}`, `/api/vehicles/{vehicle_id}/history`, `/api/identity-events`, `/api/identity-events/latest`.
* `README.md`: Updated API reference, quickstart commands, and architectural diagram.

---

## 3. Machine Learning Model & Feature Representation

| Parameter | Specification |
| :--- | :--- |
| **Model Backbone** | Pretrained `torchvision.models.resnet18` |
| **Pretrained Weights** | `ResNet18_Weights.DEFAULT` (ImageNet1K) |
| **Runtime Device** | CPU / CUDA (auto-detected) |
| **Head Modification** | Final 1000-class linear classification layer replaced with `torch.nn.Identity()` |
| **Input Resolution** | 224 x 224 pixels (RGB, ImageNet normalized) |
| **Feature Dimension** | 512 dimensions (1D floating-point vector) |
| **Normalization** | L2-normalization (\(\|v\|_2 = 1.0\)) |
| **Zero LLM Policy** | Fully compliant. Zero generative AI or LLMs used at runtime. |

---

## 4. Similarity Calculation & Decision Rules

### Cosine Similarity:
Given two L2-normalized vectors \(\mathbf{a}\) and \(\mathbf{b}\):
\[
\text{sim}(\mathbf{a}, \mathbf{b}) = \max\left(0.0, \min\left(1.0, \frac{\mathbf{a} \cdot \mathbf{b}}{\|\mathbf{a}\| \|\mathbf{b}\|}\right)\right)
\]

### Configured Calibration Thresholds:
* `IDENTITY_HIGH_THRESHOLD = 0.85` *(Empirical demo threshold for high visual consistency)*
* `IDENTITY_LOW_THRESHOLD = 0.60` *(Empirical demo threshold for appearance deviation)*

> [!NOTE]
> These thresholds are calibrated for demo evaluation and are not claimed as universal accuracy figures.

### Decision Rules:
1. **Rule A (SAME_VEHICLE):** Observed plate matches candidate canonical plate AND visual similarity \(\ge 0.85\).
2. **Rule B (POSSIBLE_IDENTITY_MISMATCH):** Observed plate matches candidate canonical plate BUT visual similarity \(< 0.85\).
3. **Rule C (POSSIBLE_PLATE_SWAP):** Observed plate differs from candidate plate BUT visual similarity \(\ge 0.85\).
4. **Rule D (PLATE_UNREADABLE_VEHICLE_MATCH):** Plate is unreadable/missing BUT visual similarity \(\ge 0.85\) with known identity.
5. **Rule E (NEW_VEHICLE):** No historical candidate match found; registers new vehicle identity (`V-XXX`).

---

## 5. Automated Verification & Test Results

### Full Test Suite (14 Tests):
* `tests/test_identity.py::test_cosine_similarity_basics` &rarr; **PASSED**
* `tests/test_identity.py::test_rule_new_vehicle` &rarr; **PASSED**
* `tests/test_identity.py::test_rule_same_vehicle` &rarr; **PASSED**
* `tests/test_identity.py::test_rule_possible_identity_mismatch` &rarr; **PASSED**
* `tests/test_identity.py::test_rule_possible_plate_swap` &rarr; **PASSED**
* `tests/test_identity.py::test_rule_plate_unreadable_vehicle_match` &rarr; **PASSED**
* `tests/test_identity.py::test_service_identity_lifecycle` &rarr; **PASSED**
* `tests/test_vtrace.py::test_video_source_initialization` &rarr; **PASSED**
* `tests/test_vtrace.py::test_invalid_video_handling` &rarr; **PASSED**
* `tests/test_vtrace.py::test_frame_processing_with_no_detection` &rarr; **PASSED**
* `tests/test_vtrace.py::test_ocr_empty_result` &rarr; **PASSED**
* `tests/test_vtrace.py::test_valid_structured_detection_event` &rarr; **PASSED**
* `tests/test_vtrace.py::test_database_insertion` &rarr; **PASSED**
* `tests/test_vtrace.py::test_evidence_image_creation` &rarr; **PASSED**

**Overall Test Suite Result:** **14/14 PASSED (100%)**

### Live Demo & API Measurements:
* Live video inference: Average 0.988 cosine similarity observed across consecutive CCTV vehicle frames.
* Status classification: `SAME_VEHICLE` generated with `MATCHED` status.
* SQLite records: Successfully persisted in `vehicle_identities`, `identity_observations`, and enriched `detections`.

---

## 6. Remaining Limitations & Next Steps
* **Lighting & Viewpoint Variation:** General-purpose ImageNet weights capture overall vehicle color and geometry well, but fine-grained metric learning (e.g. triplet loss trained on vehicle re-identification datasets like VeRi-776) can further improve discriminability between identical makes and models.
* **Temporal Tracking Smoothing:** Currently matches frame-by-frame; integrating a lightweight Kalman or centroid tracker across video frames will smooth similarity fluctuations.
