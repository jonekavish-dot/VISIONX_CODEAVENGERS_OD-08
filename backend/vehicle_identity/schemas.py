"""
IVACS V-TRACE Vehicle Identity Schemas
Defines event types, identity models, observations, and match results.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class IdentityEventType(str, Enum):
    NEW_VEHICLE = "NEW_VEHICLE"
    SAME_VEHICLE = "SAME_VEHICLE"
    POSSIBLE_IDENTITY_MISMATCH = "POSSIBLE_IDENTITY_MISMATCH"
    POSSIBLE_PLATE_SWAP = "POSSIBLE_PLATE_SWAP"
    PLATE_UNREADABLE_VEHICLE_MATCH = "PLATE_UNREADABLE_VEHICLE_MATCH"

class VehicleIdentity(BaseModel):
    id: Optional[int] = None
    vehicle_id: str
    canonical_plate: Optional[str] = None
    first_seen: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_seen: str = Field(default_factory=lambda: datetime.now().isoformat())
    visit_count: int = 1
    vehicle_class: Optional[str] = None
    color: Optional[str] = None
    embedding: Optional[List[float]] = None
    is_demo: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class IdentityObservation(BaseModel):
    id: Optional[int] = None
    vehicle_identity_id: str
    observed_plate: Optional[str] = None
    plate_confidence: Optional[float] = None
    ocr_confidence: Optional[float] = None
    visual_similarity: Optional[float] = None
    event_type: IdentityEventType
    camera_id: str = "CAM-01"
    zone: str = "GATE_IN"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    frame_number: int = 0
    vehicle_crop_path: Optional[str] = None
    plate_crop_path: Optional[str] = None
    frame_path: Optional[str] = None
    previous_crop_path: Optional[str] = None
    is_demo: bool = False

class IdentityMatchResult(BaseModel):
    vehicle_id: str
    similarity: float
    matched: bool
    event_type: IdentityEventType
    previous_crop_path: Optional[str] = None
    canonical_plate: Optional[str] = None
    details: Optional[str] = None
    is_duplicate: bool = False

class VehicleComparisonResponse(BaseModel):
    vehicle_id: str
    observed_plate: Optional[str] = None
    historical_plate: Optional[str] = None
    current_vehicle_image: Optional[str] = None
    historical_vehicle_image: Optional[str] = None
    current_plate_image: Optional[str] = None
    historical_plate_image: Optional[str] = None
    visual_similarity: float
    identity_event: str
    rule_used: str
    requires_manual_review: bool
    alert_title: str
    alert_message: str
    action_required: str
    timestamp: str
    historical_timestamp: Optional[str] = None
    camera_id: str = "CAM-01"
    zone: str = "GATE_IN"
    plate_confidence: Optional[float] = None
    ocr_confidence: Optional[float] = None

def get_alert_text(event_type: IdentityEventType, plate: Optional[str] = None) -> Dict[str, Any]:
    """
    Deterministic human-authored alert text templates.
    Zero LLM. Strict honest analytical signals.
    """
    p_str = plate or "UNKNOWN"
    if event_type == IdentityEventType.POSSIBLE_IDENTITY_MISMATCH:
        return {
            "title": "POSSIBLE PLATE–VEHICLE IDENTITY MISMATCH",
            "message": f"Observed plate {p_str} is associated with a vehicle appearance that differs from the historical vehicle profile.",
            "action": "Manual verification required.",
            "requires_manual_review": True,
            "rule": "Rule B (Same Plate + Visual Deviation)"
        }
    elif event_type == IdentityEventType.POSSIBLE_PLATE_SWAP:
        return {
            "title": "POSSIBLE PLATE SWAP",
            "message": f"Observed vehicle appearance matches a historical vehicle associated with another plate, but carries plate {p_str}.",
            "action": "Manual verification required.",
            "requires_manual_review": True,
            "rule": "Rule C (Different Plate + High Visual Similarity)"
        }
    elif event_type == IdentityEventType.PLATE_UNREADABLE_VEHICLE_MATCH:
        return {
            "title": "PLATE UNREADABLE — VEHICLE CONTINUITY FOUND",
            "message": "Observed license plate is unreadable or obscured, but vehicle visual appearance strongly matches historical profile.",
            "action": "Visual continuity recorded. Plate inspection recommended.",
            "requires_manual_review": False,
            "rule": "Rule D (Unreadable Plate + High Visual Similarity)"
        }
    elif event_type == IdentityEventType.SAME_VEHICLE:
        return {
            "title": "VERIFIED VEHICLE IDENTITY",
            "message": f"Vehicle appearance and license plate {p_str} are fully consistent with historical profile.",
            "action": "Identity confirmed.",
            "requires_manual_review": False,
            "rule": "Rule A (Same Plate + High Visual Similarity)"
        }
    else: # NEW_VEHICLE
        return {
            "title": "NEW VEHICLE REGISTERED",
            "message": f"First sighting of vehicle with plate {p_str}. Baseline identity profile established.",
            "action": "Baseline recorded.",
            "requires_manual_review": False,
            "rule": "Rule E (New Identity Registration)"
        }

class ScenarioStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"

class ScenarioStatusResponse(BaseModel):
    scenario: Optional[str] = None
    step: int = 0
    total_steps: int = 2
    status: ScenarioStatus = ScenarioStatus.IDLE
    message: Optional[str] = None
    current_observation: Optional[IdentityObservation] = None
    comparison: Optional[VehicleComparisonResponse] = None

class ScenarioStartRequest(BaseModel):
    scenario: str = "IDENTITY_MISMATCH"

class VehicleIdentityListResponse(BaseModel):
    total: int
    vehicles: List[VehicleIdentity]

class IdentityObservationListResponse(BaseModel):
    total: int
    observations: List[IdentityObservation]
