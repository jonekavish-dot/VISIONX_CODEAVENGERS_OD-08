"""
IVACS V-TRACE Alert & Unified Trust Snapshot Schemas
Defines structured schemas for security alerts, unified vehicle trust snapshots, and dashboard telemetry.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class AlertType(str, Enum):
    POSSIBLE_IDENTITY_MISMATCH = "POSSIBLE_IDENTITY_MISMATCH"
    POSSIBLE_PLATE_SWAP = "POSSIBLE_PLATE_SWAP"
    PLATE_UNREADABLE_VEHICLE_MATCH = "PLATE_UNREADABLE_VEHICLE_MATCH"
    REGISTRY_ATTRIBUTE_MISMATCH = "REGISTRY_ATTRIBUTE_MISMATCH"
    PERMIT_EXPIRED = "PERMIT_EXPIRED"
    UNAUTHORIZED_ZONE = "UNAUTHORIZED_ZONE"
    ROUTE_INTEGRITY_ANOMALY = "ROUTE_INTEGRITY_ANOMALY"
    UNKNOWN_VEHICLE = "UNKNOWN_VEHICLE"

class AlertItem(BaseModel):
    id: Optional[int] = None
    type: str
    severity: str
    vehicle_id: Optional[str] = None
    plate: Optional[str] = None
    camera_id: str
    zone: str
    timestamp: str
    title: str
    reason: str
    action_required: str
    requires_manual_review: bool = True
    evidence_references: Dict[str, Any] = Field(default_factory=dict)
    review_status: str = "PENDING"
    is_demo: bool = False

class VehicleTrustSnapshot(BaseModel):
    """
    Unified analytical snapshot combining OCR, visual identity, registry, permit, zone, and route.
    Fully explainable; zero magical 'AI trust score'.
    """
    vehicle_id: str
    plate: Optional[str] = None
    vehicle_class: Optional[str] = None
    camera_id: str
    zone: str
    timestamp: str
    identity_event: str
    visual_similarity: Optional[float] = None
    registry_status: str
    permit_status: str
    zone_status: str
    route_status: str
    overall_event: str
    requires_review: bool
    evidence: Optional[Dict[str, Any]] = None

class DashboardSummary(BaseModel):
    active_vehicles: int
    detections: int
    identity_warnings: int
    access_alerts: int
    route_alerts: int
    unreadable_plates: int

class LiveCameraCard(BaseModel):
    camera_id: str
    camera_name: str
    zone: str
    plate: str
    vehicle_class: Optional[str] = None
    status: str
    frame_path: Optional[str] = None
    vehicle_crop_path: Optional[str] = None
    plate_crop_path: Optional[str] = None
    annotated_frame_path: Optional[str] = None
    timestamp: Optional[str] = None
    identity_event: Optional[str] = None
