"""
IVACS V-TRACE Demo Scenario Manager
Coordinates and executes deterministic, repeatable identity scenarios.
Integrates directly with the real VehicleIdentityService and ResNet18 embedding engine.
Zero synthetic or hardcoded scores; 100% computed via real neural embeddings and decision rules.
"""

import os
import cv2
import time
import logging
import threading
from typing import Optional, Dict, Any
from datetime import datetime

from backend.config import SCENARIOS_DIR
from backend.demo.scenarios import DEMO_SCENARIOS, ScenarioDefinition
from backend.vehicle_identity.identity_service import VehicleIdentityService
from backend.vehicle_identity.schemas import (
    ScenarioStatus,
    ScenarioStatusResponse,
    VehicleComparisonResponse,
    IdentityObservation,
    IdentityEventType,
    get_alert_text
)
from backend.database.database import (
    reset_demo_data,
    get_vehicle_comparison,
    get_identity_observations_for_vehicle,
    get_vehicle_identity_by_id
)

logger = logging.getLogger("vtrace.scenario_manager")

class ScenarioManager:
    """State machine and runner for controlled hackathon identity scenarios."""

    def __init__(self, identity_service: Optional[VehicleIdentityService] = None):
        self.identity_service = identity_service or VehicleIdentityService()
        self.current_scenario: Optional[str] = None
        self.step: int = 0
        self.total_steps: int = 2
        self.status: ScenarioStatus = ScenarioStatus.IDLE
        self.message: str = "Ready"
        self.last_observation: Optional[IdentityObservation] = None
        self.last_comparison: Optional[VehicleComparisonResponse] = None
        self._lock = threading.Lock()

    def get_scenario_status(self) -> ScenarioStatusResponse:
        with self._lock:
            return ScenarioStatusResponse(
                scenario=self.current_scenario,
                step=self.step,
                total_steps=self.total_steps,
                status=self.status,
                message=self.message,
                current_observation=self.last_observation,
                comparison=self.last_comparison
            )

    def get_current_observation(self) -> Optional[IdentityObservation]:
        with self._lock:
            return self.last_observation

    def stop_scenario(self):
        with self._lock:
            self.status = ScenarioStatus.IDLE
            self.message = "Scenario stopped by operator."

    def reset_demo(self) -> Dict[str, Any]:
        with self._lock:
            stats = reset_demo_data()
            self.current_scenario = None
            self.step = 0
            self.status = ScenarioStatus.IDLE
            self.message = "Demo records safely cleared."
            self.last_observation = None
            self.last_comparison = None
            self.identity_service.clear_cooldown()
            self.identity_service._refresh_cache()
            return stats

    def start_scenario(self, scenario_name: str) -> ScenarioStatusResponse:
        """
        Executes a controlled 2-step demonstration scenario:
        Step 1: Baseline historical sighting (e.g. Bus + TN01AB1234)
        Step 2: Subsequent sighting (same vehicle, mismatched vehicle, swapped plate, or unreadable)
        
        Uses genuine ResNet18 embeddings and identity decision rules A-E.
        """
        norm_key = scenario_name.strip().upper()
        if norm_key not in DEMO_SCENARIOS:
            valid_keys = list(DEMO_SCENARIOS.keys())
            raise ValueError(f"Unknown scenario '{scenario_name}'. Valid options: {valid_keys}")

        definition = DEMO_SCENARIOS[norm_key]

        with self._lock:
            self.current_scenario = norm_key
            self.status = ScenarioStatus.RUNNING
            self.step = 0
            self.total_steps = len(definition.steps)
            self.message = f"Executing scenario: {definition.title}"

        logger.info(f"Starting Demo Scenario '{norm_key}': {definition.title}")

        # Ensure demo media exists on disk
        for stp in definition.steps:
            if not os.path.exists(stp.vehicle_image_path) or not os.path.exists(stp.plate_image_path):
                from scripts.setup_demo_media import setup_demo_scenarios
                setup_demo_scenarios()
                break

        # Reset cooldown to allow consecutive demo scenario steps
        self.identity_service.clear_cooldown()

        # Step 1: Baseline Historical Vehicle Observation
        s1 = definition.steps[0]
        v_img1 = cv2.imread(s1.vehicle_image_path)
        if v_img1 is None:
            raise RuntimeError(f"Failed to load image for step 1: {s1.vehicle_image_path}")

        res1 = self.identity_service.process_vehicle(
            vehicle_crop=v_img1,
            observed_plate=s1.observed_plate,
            plate_confidence=s1.plate_confidence,
            ocr_confidence=s1.ocr_confidence,
            vehicle_class=s1.vehicle_class,
            camera_id=s1.camera_id,
            zone=s1.zone,
            frame_number=101,
            timestamp=datetime.now().isoformat(),
            vehicle_crop_path=s1.vehicle_image_path,
            plate_crop_path=s1.plate_image_path,
            is_demo=True
        )
        baseline_vehicle_id = res1.vehicle_id

        with self._lock:
            self.step = 1
            self.message = f"Step 1 completed: Baseline registered ({baseline_vehicle_id})"

        # Brief pause to ensure distinct timestamp and reset cooldown
        time.sleep(0.05)
        self.identity_service.clear_cooldown()

        # Step 2: Current Vehicle Observation (Identity Comparison)
        s2 = definition.steps[1]
        v_img2 = cv2.imread(s2.vehicle_image_path)
        if v_img2 is None:
            raise RuntimeError(f"Failed to load image for step 2: {s2.vehicle_image_path}")

        res2 = self.identity_service.process_vehicle(
            vehicle_crop=v_img2,
            observed_plate=s2.observed_plate,
            plate_confidence=s2.plate_confidence,
            ocr_confidence=s2.ocr_confidence,
            vehicle_class=s2.vehicle_class,
            camera_id=s2.camera_id,
            zone=s2.zone,
            frame_number=102,
            timestamp=datetime.now().isoformat(),
            vehicle_crop_path=s2.vehicle_image_path,
            plate_crop_path=s2.plate_image_path,
            previous_crop_path=s1.vehicle_image_path,
            is_demo=True
        )

        current_vehicle_id = res2.vehicle_id

        # Fetch latest observation for response
        obs_list = get_identity_observations_for_vehicle(current_vehicle_id)
        current_obs = obs_list[0] if obs_list else None

        # Build comprehensive comparison packet
        alert_info = get_alert_text(res2.event_type, s2.observed_plate)

        # Retrieve historical image references
        hist_vehicle_crop = s1.vehicle_image_path
        hist_plate_crop = s1.plate_image_path
        hist_plate_str = s1.observed_plate

        comparison = VehicleComparisonResponse(
            vehicle_id=current_vehicle_id,
            observed_plate=s2.observed_plate,
            historical_plate=hist_plate_str,
            current_vehicle_image=s2.vehicle_image_path,
            historical_vehicle_image=hist_vehicle_crop,
            current_plate_image=s2.plate_image_path,
            historical_plate_image=hist_plate_crop,
            visual_similarity=res2.similarity,
            identity_event=res2.event_type.value,
            rule_used=alert_info.get("rule", "Analytical Rule"),
            requires_manual_review=alert_info.get("requires_manual_review", False),
            alert_title=alert_info.get("title", ""),
            alert_message=alert_info.get("message", ""),
            action_required=alert_info.get("action", ""),
            timestamp=datetime.now().isoformat(),
            historical_timestamp=datetime.now().isoformat(),
            camera_id=s2.camera_id,
            zone=s2.zone,
            plate_confidence=s2.plate_confidence,
            ocr_confidence=s2.ocr_confidence
        )

        with self._lock:
            self.step = 2
            self.status = ScenarioStatus.COMPLETED
            self.message = f"Scenario completed: {res2.event_type.value} (Similarity: {res2.similarity:.2f})"
            self.last_observation = current_obs
            self.last_comparison = comparison

        logger.info(f"Scenario '{norm_key}' completed: Event = {res2.event_type.value}, Sim = {res2.similarity:.3f}")
        return self.get_scenario_status()
