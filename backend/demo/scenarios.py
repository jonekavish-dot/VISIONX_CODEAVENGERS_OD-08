"""
IVACS V-TRACE: Demo Scenario Definitions
Explicitly defines the 4 controlled hackathon scenarios:
1. NORMAL_REPEAT: Same plate + same physical vehicle appearance => SAME_VEHICLE
2. IDENTITY_MISMATCH: Same plate + visibly different physical vehicle => POSSIBLE_IDENTITY_MISMATCH
3. PLATE_SWAP: Same physical vehicle appearance + different plate => POSSIBLE_PLATE_SWAP
4. PLATE_UNREADABLE: Vehicle visually matches historical identity but plate unreadable => PLATE_UNREADABLE_VEHICLE_MATCH

NOTE: All scenarios use real vehicle crops and real ResNet18 feature embeddings.
Marked explicitly as DEMO DATA.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pathlib import Path
from backend.config import SCENARIOS_DIR
from backend.vehicle_identity.schemas import IdentityEventType

@dataclass
class ScenarioStep:
    step_number: int
    name: str
    vehicle_image_path: str
    plate_image_path: str
    observed_plate: Optional[str]
    plate_confidence: float
    ocr_confidence: float
    vehicle_class: str
    camera_id: str
    zone: str
    is_baseline: bool = False

@dataclass
class ScenarioDefinition:
    name: str
    title: str
    description: str
    expected_event: IdentityEventType
    steps: List[ScenarioStep]

def get_scenario_definitions() -> Dict[str, ScenarioDefinition]:
    norm_dir = SCENARIOS_DIR / "normal_vehicle"
    mismatch_dir = SCENARIOS_DIR / "identity_mismatch"
    swap_dir = SCENARIOS_DIR / "plate_swap"
    unread_dir = SCENARIOS_DIR / "unreadable_plate"

    return {
        "NORMAL_REPEAT": ScenarioDefinition(
            name="NORMAL_REPEAT",
            title="Normal Vehicle Repeat Observation",
            description="Same license plate observed on identical physical vehicle appearance. Proves baseline consistency.",
            expected_event=IdentityEventType.SAME_VEHICLE,
            steps=[
                ScenarioStep(
                    step_number=1,
                    name="Baseline Sighting (Historical Vehicle)",
                    vehicle_image_path=str(norm_dir / "step1_historical_vehicle.jpg"),
                    plate_image_path=str(norm_dir / "step1_historical_plate.jpg"),
                    observed_plate="TN01AB1234",
                    plate_confidence=0.96,
                    ocr_confidence=0.94,
                    vehicle_class="bus",
                    camera_id="CAM-01",
                    zone="GATE_IN",
                    is_baseline=True
                ),
                ScenarioStep(
                    step_number=2,
                    name="Subsequent Sighting (Same Vehicle)",
                    vehicle_image_path=str(norm_dir / "step2_current_vehicle.jpg"),
                    plate_image_path=str(norm_dir / "step2_current_plate.jpg"),
                    observed_plate="TN01AB1234",
                    plate_confidence=0.95,
                    ocr_confidence=0.93,
                    vehicle_class="bus",
                    camera_id="CAM-01",
                    zone="GATE_IN",
                    is_baseline=False
                )
            ]
        ),
        "IDENTITY_MISMATCH": ScenarioDefinition(
            name="IDENTITY_MISMATCH",
            title="Plate-Vehicle Identity Mismatch (Possible Clone)",
            description="Same license plate observed on a visibly different physical vehicle. Triggers POSSIBLE_IDENTITY_MISMATCH.",
            expected_event=IdentityEventType.POSSIBLE_IDENTITY_MISMATCH,
            steps=[
                ScenarioStep(
                    step_number=1,
                    name="Baseline Sighting (Registered Bus)",
                    vehicle_image_path=str(mismatch_dir / "step1_historical_vehicle.jpg"),
                    plate_image_path=str(mismatch_dir / "step1_historical_plate.jpg"),
                    observed_plate="TN01AB1234",
                    plate_confidence=0.96,
                    ocr_confidence=0.94,
                    vehicle_class="bus",
                    camera_id="CAM-01",
                    zone="GATE_IN",
                    is_baseline=True
                ),
                ScenarioStep(
                    step_number=2,
                    name="Conflicting Sighting (Tipper Truck with Same Plate)",
                    vehicle_image_path=str(mismatch_dir / "step2_current_vehicle.jpg"),
                    plate_image_path=str(mismatch_dir / "step2_current_plate.jpg"),
                    observed_plate="TN01AB1234",
                    plate_confidence=0.95,
                    ocr_confidence=0.93,
                    vehicle_class="truck",
                    camera_id="CAM-01",
                    zone="GATE_IN",
                    is_baseline=False
                )
            ]
        ),
        "PLATE_SWAP": ScenarioDefinition(
            name="PLATE_SWAP",
            title="Vehicle Plate Swap Anomaly",
            description="Same physical vehicle appearance observed carrying a different license plate. Triggers POSSIBLE_PLATE_SWAP.",
            expected_event=IdentityEventType.POSSIBLE_PLATE_SWAP,
            steps=[
                ScenarioStep(
                    step_number=1,
                    name="Baseline Sighting (Bus registered under TN01AB1234)",
                    vehicle_image_path=str(swap_dir / "step1_historical_vehicle.jpg"),
                    plate_image_path=str(swap_dir / "step1_historical_plate.jpg"),
                    observed_plate="TN01AB1234",
                    plate_confidence=0.96,
                    ocr_confidence=0.94,
                    vehicle_class="bus",
                    camera_id="CAM-01",
                    zone="GATE_IN",
                    is_baseline=True
                ),
                ScenarioStep(
                    step_number=2,
                    name="Conflicting Sighting (Same Bus with KA05CD5678)",
                    vehicle_image_path=str(swap_dir / "step2_current_vehicle.jpg"),
                    plate_image_path=str(swap_dir / "step2_current_plate.jpg"),
                    observed_plate="KA05CD5678",
                    plate_confidence=0.94,
                    ocr_confidence=0.92,
                    vehicle_class="bus",
                    camera_id="CAM-01",
                    zone="GATE_IN",
                    is_baseline=False
                )
            ]
        ),
        "PLATE_UNREADABLE": ScenarioDefinition(
            name="PLATE_UNREADABLE",
            title="Unreadable Plate with Vehicle Continuity Match",
            description="Vehicle visually matches known identity but license plate is unreadable or obscured. Triggers PLATE_UNREADABLE_VEHICLE_MATCH.",
            expected_event=IdentityEventType.PLATE_UNREADABLE_VEHICLE_MATCH,
            steps=[
                ScenarioStep(
                    step_number=1,
                    name="Baseline Sighting (Bus with clear plate)",
                    vehicle_image_path=str(unread_dir / "step1_historical_vehicle.jpg"),
                    plate_image_path=str(unread_dir / "step1_historical_plate.jpg"),
                    observed_plate="TN01AB1234",
                    plate_confidence=0.96,
                    ocr_confidence=0.94,
                    vehicle_class="bus",
                    camera_id="CAM-01",
                    zone="GATE_IN",
                    is_baseline=True
                ),
                ScenarioStep(
                    step_number=2,
                    name="Muddy / Blurred Sighting (Same Bus with Obscured Plate)",
                    vehicle_image_path=str(unread_dir / "step2_current_vehicle.jpg"),
                    plate_image_path=str(unread_dir / "step2_current_plate.jpg"),
                    observed_plate=None,
                    plate_confidence=0.0,
                    ocr_confidence=0.0,
                    vehicle_class="bus",
                    camera_id="CAM-01",
                    zone="GATE_IN",
                    is_baseline=False
                )
            ]
        )
    }

DEMO_SCENARIOS = get_scenario_definitions()
