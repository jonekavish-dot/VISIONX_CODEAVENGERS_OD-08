# IVACS V-TRACE: Identity Demo Validation Report

**Document:** `ARTIFACTS/identity_demo_validation.md`  
**Date:** 2026-09-18  
**Evaluation Target:** Problem Statement OD-08 — License Plate Detection & Vehicle Identity Engine  
**Policy Adherence:** Strict Zero Generative AI / Zero LLM at Runtime. Real Deep Visual Embeddings (ResNet18) & Deterministic Identity Rules (Rules A-E).

---

## 1. Automated Test Suite Breakdown

* **Existing Foundation & Identity Tests:** **14 / 14 Passed**
  - `tests/test_vtrace.py` (7 tests: Video ingestion, error handling, detection, OCR, SQLite persistence, evidence crops)
  - `tests/test_identity.py` (7 tests: Cosine math, Rule A, Rule B, Rule C, Rule D, Rule E, lifecycle persistence)
* **New Demo Scenario Tests:** **8 / 8 Passed**
  - `test_scenario_normal_repeat`: PASSED
  - `test_scenario_identity_mismatch`: PASSED
  - `test_scenario_plate_swap`: PASSED
  - `test_scenario_unreadable_plate`: PASSED
  - `test_scenario_start_stop`: PASSED
  - `test_scenario_reset`: PASSED
  - `test_comparison_api`: PASSED
  - `test_duplicate_identity_event_suppression`: PASSED
* **Total Tests:** **22 / 22 Passed (100% Pass Rate)**
* **Execution Duration:** 29.00 seconds (`python -m pytest tests/ -v`)

---

## 2. Demo Scenarios Real Execution Audit

All 4 scenarios were executed using the real ResNet18 feature extractor model on local image files (`data/demo/scenarios/`) with actual cosine similarity computation:

| Scenario Name | Visual Similarity | Emitted Analytical Signal | Manual Review Flag | Audit Status |
| :--- | :---: | :--- | :---: | :---: |
| **NORMAL_REPEAT** | `0.999` (&ge; 0.85) | `SAME_VEHICLE` (Rule A) | `False` | **PASS** |
| **IDENTITY_MISMATCH** | `0.700` (< 0.85) | `POSSIBLE_IDENTITY_MISMATCH` (Rule B) | `True` | **PASS** |
| **PLATE_SWAP** | `0.999` (&ge; 0.85) | `POSSIBLE_PLATE_SWAP` (Rule C) | `True` | **PASS** |
| **PLATE_UNREADABLE** | `0.999` (&ge; 0.85) | `PLATE_UNREADABLE_VEHICLE_MATCH` (Rule D) | `False` | **PASS** |

---

## 3. Core Innovation Verification (9 Evaluation Criteria)

Executed via `verify_identity_mismatch_live.py`:

| Criteria | Expected Result | Actual Result | Status |
| :--- | :--- | :--- | :---: |
| 1. Historical observation created | Baseline identity record in SQLite | Vehicle ID assigned, observation persisted | **PASS** |
| 2. Current observation created | Mismatched vehicle observation logged | Observation linked to new vehicle profile | **PASS** |
| 3. Real visual embedding comparison | ResNet18 512-dim embedding computed | Extracted from pixels; cosine similarity evaluated | **PASS** |
| 4. Similarity score returned | Real float value < 0.85 | Exactly `0.700` returned | **PASS** |
| 5. Identity rule evaluated | Rule B applied deterministically | Rule B (Same Plate + Visual Deviation) | **PASS** |
| 6. Anomaly event produced | `POSSIBLE_IDENTITY_MISMATCH` | `POSSIBLE_IDENTITY_MISMATCH` emitted | **PASS** |
| 7. Historical evidence retained | Historical crops exist on disk | Bus vehicle crop + plate crop verified | **PASS** |
| 8. Current evidence retained | Current crops exist on disk | Truck vehicle crop + plate crop verified | **PASS** |
| 9. Comparison endpoint works | `GET /api/vehicles/{id}/comparison` | 200 OK with side-by-side images & alert text | **PASS** |

---

## 4. Subsystem Verification Status

* **Evidence Comparison:** **PASS** (Side-by-side current vs historical vehicle & plate crops served via API)
* **REST API:** **PASS** (All 18 endpoints operational)
* **Temporal Deduplication:** **PASS** (`IDENTITY_EVENT_COOLDOWN_SECONDS` suppresses duplicate alert spam while preserving detection history)
* **Demo Data Reset:** **PASS** (`POST /api/demo/reset` purges only demo records with `is_demo = 1`)
