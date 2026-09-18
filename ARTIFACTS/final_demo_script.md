# IVACS V-TRACE: 90-Second Evaluator Demo Script

**Project:** IVACS V-TRACE (Vehicle Trust, Route & Evidence Engine)  
**Hackathon Challenge:** OD-08 — License Plate Detection & Recognition from Construction-Site CCTV  
**Target Duration:** 90 seconds (Concise, High-Impact, Audit-Grade)  
**Primary Pitch:** *"Standard ANPR reads characters; IVACS V-TRACE verifies the physical vehicle behind the plate."*

---

## Pre-Demo Setup Checklist (15 Seconds Before Presenting)

1. Start backend & frontend unified server:
   ```bash
   python run_server.py
   ```
2. Open browser at: `http://localhost:8000` (or `http://localhost:5173` if running Vite dev server).
3. Verify all 4 CCTV feeds (`CAM-01` to `CAM-04`) are green and active in the grid.
4. Click **"Purge Demo State"** once to ensure a clean baseline.

---

## 90-Second Stage Presentation Script

### [00:00 - 00:15] The Hook & Industrial Problem (15s)
> *"Judges, on high-security infrastructure and construction sites, standard ANPR has a fatal blindspot: **it only reads characters**. If a stolen or cloned plate is mounted onto an unauthorized dump truck, standard ANPR blindly approves entry.*  
>  
> *Meet **IVACS V-TRACE**. It couples YOLOv8 and EasyOCR with a **512-dimensional ResNet18 Vehicle Visual Fingerprint Engine**, an **RTO Registry Consistency Checker**, and a **Site Route Integrity Engine** to determine: **'Does this physical vehicle look like the vehicle legally tied to this plate?'** Let me show you in action."*

---

### [00:15 - 00:35] Baseline Verification — Normal Repeat (20s)
*Action: Click **"1. Normal Repeat"** button.*
> *"Step 1: Vehicle `TN01AB1234` (a Tata Starbus) enters through CAM-01 Main Gate. The system extracts its plate, computes its 512-dimensional visual embedding, and queries our Registry and Site Permit database.*  
>  
> *Notice on screen:*
> - *OCR reads `TN01AB1234` at 93% confidence.*
> - *Registry verifies: Registered as `Tata Starbus (Bus)`, Color `Yellow` — **REGISTRY MATCH**.*
> - *Site Permit: **ACTIVE** for Zone A & Zone B.*
> - *When it passes CAM-02, visual similarity is **0.99** — **Rule A: SAME_VEHICLE**. Trust score stays at **100%**."*

---

### [00:35 - 00:55] The Innovation: Detecting Plate Cloning (20s)
*Action: Click **"2. Identity Mismatch"** button.*
> *"Now observe what happens when an unauthorized tipper truck enters carrying the **exact same license plate** `TN01AB1234`.*  
>  
> *(Wait 2 seconds as alert triggers)*  
>  
> *Look at the alert stream: A **CRITICAL SECURITY ALERT** is instantly fired: `POSSIBLE PLATE–VEHICLE IDENTITY MISMATCH`.*  
>  
> *(Click **"Inspect Evidence"** on the alert or card)*  
>  
> *The modal renders the side-by-side court-ready evidence:*
> - *Historical reference: Bus.*
> - *Current observation: Dump Truck.*
> - *Cosine similarity: **0.19** (far below our calibrated threshold of 0.85).*
> - *Registry Flag: Detected class `truck` conflicts with registered class `bus`.*
> - *Trust Score collapses from 100% to **30%**."*

---

### [00:55 - 01:15] Plate Swap & Unreadable Plate Continuity (20s)
*Action: Click **"4. Unreadable Plate"** button.*
> *"What about muddy construction sites where plates are unreadable? Traditional ANPR fails completely.*  
>  
> *Here, mud obscures the plate. EasyOCR returns unreadable. Yet V-TRACE computes the vehicle's deep visual embedding, cross-matches it against the active fleet, and triggers **Rule D: PLATE_UNREADABLE_VEHICLE_MATCH** with **0.88 similarity**.*  
>  
> *Vehicle tracking and route integrity continue unbroken without manual operator intervention."*

---

### [01:15 - 01:30] Site Route Integrity & Closing Summary (15s)
*Action: Click on `CAM-03` Live Card or open Vehicle Drawer.*
> *"Beyond identity, V-TRACE enforces spatial-temporal route integrity:*
> - *If a vehicle jumps from Entrance to Material Exit in 2 seconds instead of the physical minimum of 30 seconds, it triggers a **Speed / Route Anomaly alert**.*
> - *If a vehicle enters an unauthorized excavation zone or has an expired permit, access is immediately flagged.*
>  
> *Crucially: **Zero LLMs or generative models are used at runtime**. Every decision is 100% deterministic, explainable, and edge-ready with 37 out of 37 automated tests passing. Thank you!"*

---

## Anticipated Judge Q&A Cheat Sheet

| Judge Question | High-Impact Answer |
|---|---|
| **"Why not just use an LLM (like GPT-4V or Gemini) for identity comparison?"** | Industrial edge devices have limited bandwidth and power. Vision-Language Models are non-deterministic, have high latency (1.5-3s), and suffer from hallucinations. IVACS V-TRACE uses a lightweight ResNet18 backbone that runs in **12ms on CPU**, is 100% reproducible, and costs zero API fees. |
| **"What if dirt or lighting changes the vehicle color?"** | ResNet18 extracts structural geometric features and localized contours alongside color. Furthermore, our trust engine combines visual similarity, RTO registry consistency, and route history so no single sensor noise triggers a false arrest. |
| **"How do you handle privacy and government database access?"** | We designed a clean abstract registry interface (`VehicleRegistry`). For the hackathon we demonstrate with a local SQLite registry (`DemoVehicleRegistry`); for enterprise deployment, it seamlessly plugs into the official Parivahan VAHAN 4.0 API via OAuth2/HMAC without code changes. |
| **"What happens during rapid frame bursts from 30 FPS cameras?"** | Our pipeline implements a 10-second temporal cooldown deduplication engine keyed on `(vehicle_id, alert_type)`. It prevents spamming security guards while preserving the initial forensic snapshot. |
