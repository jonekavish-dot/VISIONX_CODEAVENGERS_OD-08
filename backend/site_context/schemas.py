"""
IVACS V-TRACE Site Context Schemas
Defines structured schemas for permits, zones, and route integrity validation.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class PermitCheckStatus(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    PERMIT_EXPIRED = "PERMIT_EXPIRED"
    UNAUTHORIZED_ZONE = "UNAUTHORIZED_ZONE"
    NO_SITE_PERMIT = "NO_SITE_PERMIT"
    UNKNOWN_VEHICLE = "UNKNOWN_VEHICLE"

class SitePermit(BaseModel):
    id: Optional[int] = None
    plate: str
    site_id: str = "SITE-BLR-01"
    allowed_zones: List[str] = Field(default_factory=list)
    valid_from: str
    valid_until: str
    purpose: str
    status: str = "ACTIVE"
    is_demo: bool = True

class PermitCheckResult(BaseModel):
    status: PermitCheckStatus
    permit: Optional[SitePermit] = None
    reason: str
    allowed_zones: List[str] = Field(default_factory=list)
    current_zone: str

class RouteStatus(str, Enum):
    NORMAL = "NORMAL"
    ROUTE_INTEGRITY_ANOMALY = "ROUTE_INTEGRITY_ANOMALY"

class RouteCheckResult(BaseModel):
    status: RouteStatus
    is_anomaly: bool
    reason: Optional[str] = None
    previous_zone: Optional[str] = None
    current_zone: str
    elapsed_seconds: Optional[float] = None
    min_expected_seconds: Optional[int] = None

class CameraZoneConfig(BaseModel):
    camera_id: str
    name: str
    zone: str
    description: str

class RouteRule(BaseModel):
    id: Optional[int] = None
    from_zone: str
    to_zone: str
    minimum_travel_seconds: int
    maximum_travel_seconds: int
    enabled: bool = True
