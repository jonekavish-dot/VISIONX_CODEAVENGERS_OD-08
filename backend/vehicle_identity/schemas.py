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

class IdentityMatchResult(BaseModel):
    vehicle_id: str
    similarity: float
    matched: bool
    event_type: IdentityEventType
    previous_crop_path: Optional[str] = None
    canonical_plate: Optional[str] = None
    details: Optional[str] = None

class VehicleIdentityListResponse(BaseModel):
    total: int
    vehicles: List[VehicleIdentity]

class IdentityObservationListResponse(BaseModel):
    total: int
    observations: List[IdentityObservation]
