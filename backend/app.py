"""
IVACS V-TRACE FastAPI Backend Application
Exposes REST API endpoints for CCTV vehicle/plate detection, event retrieval, and background demo streaming.
"""

import os
import time
import logging
import threading
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

import cv2
import numpy as np
import torch
from fastapi import FastAPI, BackgroundTasks, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from fastapi.responses import FileResponse
from backend.config import (
    BASE_DIR,
    DEFAULT_DEMO_VIDEO,
    PROCESS_EVERY_N_FRAMES,
    CAMERAS,
    DEFAULT_CAMERA_ID,
    EVIDENCE_DIR,
    DEMO_DIR,
    SCENARIOS_DIR
)
from backend.schemas.detection import (
    DetectionEvent,
    DetectionListResponse,
    DemoStatusResponse,
    HealthResponse,
    ProcessingStatus
)
from backend.database.database import (
    init_db,
    get_all_detections,
    get_latest_detection,
    get_total_detections_count,
    get_all_vehicle_identities,
    get_vehicle_identity_by_id,
    get_identity_observations_for_vehicle,
    get_all_identity_observations,
    get_latest_identity_observation,
    get_identity_observation_by_id,
    get_vehicle_comparison,
    reset_demo_data,
    reset_demo_registry_data,
    get_all_permits,
    get_permits_for_plate,
    get_latest_observations_by_camera
)
from backend.vehicle_identity.schemas import (
    VehicleIdentity,
    IdentityObservation,
    VehicleIdentityListResponse,
    IdentityObservationListResponse,
    VehicleComparisonResponse,
    ScenarioStatusResponse,
    ScenarioStartRequest
)
from backend.vehicle_registry import VehicleRegistryService, VehicleRegistryRecord
from backend.site_context import SiteContextService, SitePermit
from backend.alerts import (
    AlertService,
    AlertItem,
    VehicleTrustSnapshot,
    DashboardSummary,
    LiveCameraCard
)
from backend.demo.scenario_manager import ScenarioManager
from backend.video.mp4_source import MP4Source
from backend.services.frame_processor import FrameProcessor


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("vtrace.api")

# Thread-safe Demo Runner
class DemoRunner:
    def __init__(self):
        self.is_running = False
        self.camera_id = DEFAULT_CAMERA_ID
        self.video_source = DEFAULT_DEMO_VIDEO
        self.current_frame = 0
        self.total_frames = 0
        self.processed_count = 0
        self.detections_count = 0
        self.fps = 0.0
        self.message = "Idle"
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.lock = threading.Lock()

    def get_status(self) -> DemoStatusResponse:
        with self.lock:
            return DemoStatusResponse(
                is_running=self.is_running,
                camera_id=self.camera_id,
                video_source=self.video_source,
                current_frame=self.current_frame,
                total_frames=self.total_frames,
                processed_count=self.processed_count,
                detections_count=self.detections_count,
                fps=round(self.fps, 1),
                message=self.message
            )

    def start(self, video_path: Optional[str] = None, camera_id: str = DEFAULT_CAMERA_ID) -> bool:
        with self.lock:
            if self.is_running:
                return False

            self.video_source = video_path or DEFAULT_DEMO_VIDEO
            self.camera_id = camera_id
            self.current_frame = 0
            self.processed_count = 0
            self.detections_count = 0
            self.is_running = True
            self.message = f"Processing started on {self.camera_id}"
            self._stop_event.clear()

            self._thread = threading.Thread(
                target=self._run_pipeline,
                args=(self.video_source, self.camera_id),
                daemon=True
            )
            self._thread.start()
            return True

    def stop(self):
        with self.lock:
            if not self.is_running:
                return
            self._stop_event.set()
            self.message = "Stopping demo runner..."

    def _run_pipeline(self, video_path: str, camera_id: str):
        logger.info(f"DemoRunner started on {video_path} (Camera: {camera_id})")
        
        if not os.path.exists(video_path):
            with self.lock:
                self.is_running = False
                self.message = f"Error: Demo video not found at '{video_path}'. Please place MP4 in data/demo/."
            logger.error(self.message)
            return

        source = MP4Source(video_path, camera_id=camera_id)
        if not source.open():
            with self.lock:
                self.is_running = False
                self.message = f"Failed to open video file: {video_path}"
            return

        with self.lock:
            self.total_frames = source.get_total_frames()

        start_time = time.time()
        frames_since_start = 0

        try:
            for frame_num, frame in source.stream_frames(sample_every_n=PROCESS_EVERY_N_FRAMES):
                if self._stop_event.is_set():
                    logger.info("DemoRunner stop requested by user.")
                    break

                frames_since_start += 1
                now = time.time()
                elapsed = now - start_time
                current_fps = frames_since_start / max(0.001, elapsed)

                # Process single frame
                events, annotated_frame = frame_processor.process_frame(
                    frame=frame,
                    frame_number=frame_num,
                    camera_id=camera_id,
                    save_evidence=True
                )

                det_count = sum(1 for e in events if e.status == ProcessingStatus.DETECTED)

                with self.lock:
                    self.current_frame = frame_num
                    self.processed_count += 1
                    self.detections_count += det_count
                    self.fps = current_fps
                    self.message = f"Processing frame {frame_num}/{self.total_frames} (Detections: {self.detections_count})"

            with self.lock:
                self.message = f"Finished. Processed {self.processed_count} frames, {self.detections_count} detections."
        except Exception as e:
            logger.error(f"Error in DemoRunner processing loop: {e}", exc_info=True)
            with self.lock:
                self.message = f"Error during processing: {str(e)}"
        finally:
            source.close()
            with self.lock:
                self.is_running = False
            logger.info("DemoRunner loop ended.")


# App Lifecycle
frame_processor: Optional[FrameProcessor] = None
demo_runner = DemoRunner()
registry_service = VehicleRegistryService()
context_service = SiteContextService()
alert_service = AlertService(registry_service=registry_service, context_service=context_service)
scenario_manager = ScenarioManager(alert_service=alert_service)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global frame_processor, scenario_manager
    logger.info("Initializing IVACS V-TRACE Backend...")
    init_db()
    # Initialize shared FrameProcessor
    frame_processor = FrameProcessor()
    scenario_manager.identity_service = frame_processor.identity_service
    scenario_manager.alert_service = alert_service
    logger.info("IVACS V-TRACE frame processor and scenario manager initialized.")
    yield
    logger.info("Shutting down IVACS V-TRACE Backend...")
    demo_runner.stop()
    scenario_manager.stop_scenario()

app = FastAPI(
    title="IVACS V-TRACE API",
    description="Vehicle Trust, Route & Evidence Engine (Problem Statement OD-08)",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount evidence directory for serving images directly to UI / judges
app.mount("/evidence", StaticFiles(directory=str(EVIDENCE_DIR)), name="evidence")
if SCENARIOS_DIR.exists():
    app.mount("/scenarios", StaticFiles(directory=str(SCENARIOS_DIR)), name="scenarios")


# 1. Health Endpoint
@app.get("/api/health", response_model=HealthResponse)
def health_check():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return HealthResponse(
        status="healthy",
        service="IVACS V-TRACE Engine",
        version="1.0.0",
        runtime_device=device,
        models_loaded=(frame_processor is not None)
    )

# 2. Detections List Endpoint
@app.get("/api/detections", response_model=DetectionListResponse)
def get_detections(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    total = get_total_detections_count()
    items = get_all_detections(limit=limit, offset=offset)
    return DetectionListResponse(total=total, detections=items)

# 3. Latest Detection Endpoint
@app.get("/api/detections/latest", response_model=Optional[DetectionEvent])
def get_latest():
    latest = get_latest_detection()
    return latest

# 4. Demo Start Endpoint
@app.post("/api/demo/start")
def start_demo(
    video_path: Optional[str] = None,
    camera_id: str = DEFAULT_CAMERA_ID
):
    target_path = video_path or DEFAULT_DEMO_VIDEO
    if not os.path.exists(target_path):
        raise HTTPException(
            status_code=404,
            detail=f"Demo video not found at '{target_path}'. Please place MP4 in data/demo/construction_site.mp4"
        )

    started = demo_runner.start(video_path=target_path, camera_id=camera_id)
    if not started:
        raise HTTPException(
            status_code=409,
            detail="Demo runner is already active."
        )

    return {"message": "Demo started successfully", "camera_id": camera_id, "video_source": target_path}

# 5. Demo Stop Endpoint
@app.post("/api/demo/stop")
def stop_demo():
    demo_runner.stop()
    return {"message": "Demo stop requested"}

# 6. Demo Status Endpoint
@app.get("/api/demo/status", response_model=DemoStatusResponse)
def get_demo_status():
    return demo_runner.get_status()

# 7. Cameras Endpoint
@app.get("/api/cameras")
def get_cameras():
    return list(CAMERAS.values())

# 8. Vehicle Identities List Endpoint
@app.get("/api/vehicles", response_model=VehicleIdentityListResponse)
def get_vehicles():
    identities = get_all_vehicle_identities()
    return VehicleIdentityListResponse(total=len(identities), vehicles=identities)

# 9. Single Vehicle Identity Endpoint
@app.get("/api/vehicles/{vehicle_id}", response_model=VehicleIdentity)
def get_vehicle(vehicle_id: str):
    identity = get_vehicle_identity_by_id(vehicle_id)
    if not identity:
        raise HTTPException(status_code=404, detail=f"Vehicle identity '{vehicle_id}' not found.")
    return identity

# 10. Vehicle Observation History Endpoint
@app.get("/api/vehicles/{vehicle_id}/history", response_model=List[IdentityObservation])
def get_vehicle_history(vehicle_id: str):
    observations = get_identity_observations_for_vehicle(vehicle_id)
    return observations

# 11. Identity Events List Endpoint
@app.get("/api/identity-events", response_model=IdentityObservationListResponse)
def get_identity_events(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    items = get_all_identity_observations(limit=limit, offset=offset)
    return IdentityObservationListResponse(total=len(items), observations=items)

# 12. Latest Identity Event Endpoint
@app.get("/api/identity-events/latest", response_model=Optional[IdentityObservation])
def get_latest_identity_event():
    return get_latest_identity_observation()

# 13. Single Identity Event By ID Endpoint
@app.get("/api/identity-events/{id}", response_model=IdentityObservation)
def get_identity_event_by_id_endpoint(id: int):
    obs = get_identity_observation_by_id(id)
    if not obs:
        raise HTTPException(status_code=404, detail=f"Identity event with ID {id} not found.")
    return obs

# 14. Vehicle Visual Evidence Comparison Endpoint
@app.get("/api/vehicles/{vehicle_id}/comparison", response_model=VehicleComparisonResponse)
def get_vehicle_comparison_endpoint(vehicle_id: str):
    comp = get_vehicle_comparison(vehicle_id)
    if not comp:
        raise HTTPException(status_code=404, detail=f"Visual comparison data for vehicle '{vehicle_id}' not found.")
    return comp

# 15. Demo Scenario Start Endpoint
@app.post("/api/demo/scenario/start", response_model=ScenarioStatusResponse)
def start_demo_scenario(req: ScenarioStartRequest):
    try:
        status = scenario_manager.start_scenario(req.scenario)
        return status
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as ex:
        logger.error(f"Failed to execute demo scenario: {ex}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scenario execution failed: {str(ex)}")

# 16. Demo Scenario Stop Endpoint
@app.post("/api/demo/scenario/stop")
def stop_demo_scenario():
    scenario_manager.stop_scenario()
    return {"message": "Demo scenario stopped successfully"}

# 17. Demo Scenario Status Endpoint
@app.get("/api/demo/scenario/status", response_model=ScenarioStatusResponse)
def get_demo_scenario_status():
    return scenario_manager.get_scenario_status()

# 18. Demo Data Reset Endpoint (Safely clears only DEMO data)
@app.post("/api/demo/reset")
def reset_demo_endpoint():
    deleted_stats = scenario_manager.reset_demo()
    return {
        "status": "success",
        "message": "Demo scenario data safely reset. Production records and database structure preserved.",
        "deleted_records": deleted_stats
    }

# 19. Dashboard Summary Metrics Endpoint
@app.get("/api/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary_endpoint():
    return alert_service.get_dashboard_summary()

# 20. Dashboard Live Camera Feeds Endpoint
@app.get("/api/dashboard/live", response_model=Dict[str, LiveCameraCard])
def get_dashboard_live_endpoint():
    return get_latest_observations_by_camera()

# 21. Vehicle Trust Snapshot Endpoint
@app.get("/api/vehicles/{vehicle_id}/trust-snapshot", response_model=VehicleTrustSnapshot)
def get_vehicle_trust_snapshot_endpoint(vehicle_id: str):
    snapshot = alert_service.get_trust_snapshot(vehicle_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Trust snapshot for vehicle '{vehicle_id}' not found.")
    return snapshot

# 22. Security Alerts List Endpoint
@app.get("/api/alerts", response_model=List[AlertItem])
def get_alerts_endpoint(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    plate: Optional[str] = None,
    camera_id: Optional[str] = None,
    zone: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None
):
    return alert_service.get_alerts(
        limit=limit,
        offset=offset,
        plate=plate,
        camera_id=camera_id,
        zone=zone,
        alert_type=alert_type,
        severity=severity
    )

# 23. Single Alert By ID Endpoint
@app.get("/api/alerts/{id}", response_model=AlertItem)
def get_alert_by_id_endpoint(id: int):
    al = alert_service.get_alert_by_id(id)
    if not al:
        raise HTTPException(status_code=404, detail=f"Alert with ID {id} not found.")
    return al

# 24. Vehicle Registry Lookup Endpoint
@app.get("/api/registry/vehicle/{plate}", response_model=VehicleRegistryRecord)
def get_registry_vehicle_endpoint(plate: str):
    rec = registry_service.get_vehicle_by_plate(plate)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Plate '{plate}' not found in demo vehicle registry.")
    return rec

# 25. Reset Demo Vehicle Registry Endpoint
@app.post("/api/demo/registry/reset")
def reset_demo_registry_endpoint():
    count = reset_demo_registry_data()
    return {"status": "success", "message": "Demo vehicle registry reset to seed values.", "reseeded_records": count}

# 26. Site Permits List Endpoint
@app.get("/api/permits", response_model=List[SitePermit])
def get_all_permits_endpoint(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    rows = get_all_permits(limit=limit, offset=offset)
    return [SitePermit(**r) for r in rows]

# 27. Single Vehicle Permit Endpoint
@app.get("/api/permits/{plate}", response_model=List[SitePermit])
def get_vehicle_permits_endpoint(plate: str):
    rows = get_permits_for_plate(plate)
    return [SitePermit(**r) for r in rows]

# 28. Universal Media Asset Serving Endpoint
@app.get("/api/media")
def get_media_file(path: str = Query(..., description="File path to media image")):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Media file '{path}' not found.")
    return FileResponse(path)

# 29. Mount Frontend Command Center Web Application
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


