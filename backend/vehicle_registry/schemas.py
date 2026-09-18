"""
IVACS V-TRACE Vehicle Registry Schemas
Defines structured records for vehicle registration and deterministic consistency checks.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class RegistryConsistencyStatus(str, Enum):
    REGISTRY_MATCH = "REGISTRY_MATCH"
    REGISTRY_ATTRIBUTE_MISMATCH = "REGISTRY_ATTRIBUTE_MISMATCH"
    REGISTRY_RECORD_NOT_FOUND = "REGISTRY_RECORD_NOT_FOUND"
    REGISTRY_LOOKUP_UNAVAILABLE = "REGISTRY_LOOKUP_UNAVAILABLE"

class VehicleRegistryRecord(BaseModel):
    """
    Standard vehicle registry record schema.
    Strictly marked with source and is_demo flag.
    Only fields actually available in the demo registry are populated; otherwise null.
    """
    plate: str
    registration_date: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    colour: Optional[str] = None
    vehicle_type: Optional[str] = None
    fuel_type: Optional[str] = None
    insurance_status: Optional[str] = None
    fitness_status: Optional[str] = None
    pucc_status: Optional[str] = None
    source: str = "DEMO_REGISTRY"
    is_demo: bool = True

class RegistryConsistencyResult(BaseModel):
    """
    Deterministic result comparing CCTV observations with registry record.
    Uses honest analytical qualification language.
    """
    status: RegistryConsistencyStatus
    message: str
    record: Optional[VehicleRegistryRecord] = None
    mismatched_attributes: List[str] = Field(default_factory=list)
    is_demo: bool = True
