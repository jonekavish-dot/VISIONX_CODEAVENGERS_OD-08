"""
IVACS V-TRACE Demo Vehicle Registry Implementation
Queries local demonstration vehicle registry table in SQLite.
All records are synthetic/demo records and strictly marked is_demo = True.
"""

import logging
from typing import Optional
from backend.vehicle_registry.base_registry import VehicleRegistry
from backend.vehicle_registry.schemas import VehicleRegistryRecord
from backend.database.database import get_registry_record_by_plate

logger = logging.getLogger("vtrace.demo_registry")

class DemoVehicleRegistry(VehicleRegistry):
    """
    Local demonstration registry querying SQLite table vehicle_registry.
    Does NOT access government or third-party servers.
    """

    def get_vehicle_by_plate(self, plate: str) -> Optional[VehicleRegistryRecord]:
        if not plate:
            return None
        clean_plate = plate.strip().upper().replace(" ", "").replace("-", "")
        row = get_registry_record_by_plate(clean_plate)
        if not row:
            return None

        return VehicleRegistryRecord(
            plate=row.get("plate", clean_plate),
            registration_date=row.get("registration_date"),
            manufacturer=row.get("manufacturer"),
            model=row.get("model"),
            colour=row.get("colour"),
            vehicle_type=row.get("vehicle_type"),
            fuel_type=row.get("fuel_type"),
            insurance_status=row.get("insurance_status"),
            fitness_status=row.get("fitness_status"),
            pucc_status=row.get("pucc_status"),
            source=row.get("source", "DEMO_REGISTRY"),
            is_demo=bool(row.get("is_demo", 1))
        )
