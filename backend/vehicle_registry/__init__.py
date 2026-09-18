"""
IVACS V-TRACE Vehicle Registry Module
Exports registry services, schemas, and base abstractions.
"""

from backend.vehicle_registry.schemas import (
    VehicleRegistryRecord,
    RegistryConsistencyResult,
    RegistryConsistencyStatus
)
from backend.vehicle_registry.base_registry import VehicleRegistry
from backend.vehicle_registry.demo_registry import DemoVehicleRegistry
from backend.vehicle_registry.vahan_registry import VahanVehicleRegistry
from backend.vehicle_registry.registry_service import VehicleRegistryService

__all__ = [
    "VehicleRegistry",
    "DemoVehicleRegistry",
    "VahanVehicleRegistry",
    "VehicleRegistryService",
    "VehicleRegistryRecord",
    "RegistryConsistencyResult",
    "RegistryConsistencyStatus"
]
