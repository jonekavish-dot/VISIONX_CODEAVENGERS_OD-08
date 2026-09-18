"""
IVACS V-TRACE Vehicle Registry Service
Coordinates registry lookups and deterministic consistency comparisons between
real-time CCTV visual detections and registry records.
"""

import logging
from typing import Optional, List
from backend.vehicle_registry.base_registry import VehicleRegistry
from backend.vehicle_registry.demo_registry import DemoVehicleRegistry
from backend.vehicle_registry.schemas import (
    VehicleRegistryRecord,
    RegistryConsistencyResult,
    RegistryConsistencyStatus
)

logger = logging.getLogger("vtrace.registry_service")

# Class compatibility map
VEHICLE_CLASS_GROUPS = {
    "car": {"car", "sedan", "hatchback", "suv", "van", "coupe", "light motor vehicle", "lmv"},
    "truck": {"truck", "lorry", "tipper", "heavy goods vehicle", "hgv", "commercial vehicle", "pickup"},
    "bus": {"bus", "minibus", "coach", "heavy passenger vehicle"},
    "motorcycle": {"motorcycle", "scooter", "two-wheeler", "bike"}
}

class VehicleRegistryService:
    """
    Central vehicle registry service abstraction.
    All application components query through this service; never through direct DB access.
    """

    def __init__(self, registry: Optional[VehicleRegistry] = None):
        self.registry = registry or DemoVehicleRegistry()

    def get_vehicle_by_plate(self, plate: str) -> Optional[VehicleRegistryRecord]:
        """Queries the active vehicle registry."""
        if not plate:
            return None
        return self.registry.get_vehicle_by_plate(plate)

    def check_consistency(
        self,
        observed_plate: Optional[str],
        observed_class: Optional[str] = None,
        observed_colour: Optional[str] = None
    ) -> RegistryConsistencyResult:
        """
        Compares CCTV observations (plate, class, colour) against registry record.
        Returns deterministic consistency evaluation with honest analytical phrasing.
        """
        if not observed_plate:
            return RegistryConsistencyResult(
                status=RegistryConsistencyStatus.REGISTRY_LOOKUP_UNAVAILABLE,
                message="No plate text available for registry consistency verification.",
                record=None,
                mismatched_attributes=[]
            )

        clean_plate = observed_plate.strip().upper().replace(" ", "").replace("-", "")
        record = self.get_vehicle_by_plate(clean_plate)

        if not record:
            return RegistryConsistencyResult(
                status=RegistryConsistencyStatus.REGISTRY_RECORD_NOT_FOUND,
                message=f"Plate '{clean_plate}' not found in demonstration registry records.",
                record=None,
                mismatched_attributes=["plate"]
            )

        mismatches: List[str] = []

        # 1. Compare vehicle class/type
        if observed_class and record.vehicle_type:
            obs_c = observed_class.strip().lower()
            reg_t = record.vehicle_type.strip().lower()
            
            # Check if both belong to same group
            matched_group = False
            for grp_key, grp_members in VEHICLE_CLASS_GROUPS.items():
                if obs_c in grp_members and reg_t in grp_members:
                    matched_group = True
                    break
                if obs_c == grp_key and reg_t in grp_members:
                    matched_group = True
                    break

            if not matched_group and obs_c != reg_t:
                mismatches.append(f"vehicle_class (CCTV: {obs_c.upper()}, Registry: {reg_t.upper()})")

        # 2. Compare vehicle colour if observed
        if observed_colour and record.colour:
            obs_col = observed_colour.strip().upper()
            reg_col = record.colour.strip().upper()
            if obs_col != reg_col:
                mismatches.append(f"colour (CCTV: {obs_col}, Registry: {reg_col})")

        if mismatches:
            mismatch_str = ", ".join(mismatches)
            return RegistryConsistencyResult(
                status=RegistryConsistencyStatus.REGISTRY_ATTRIBUTE_MISMATCH,
                message=f"Attribute mismatch detected: {mismatch_str}.",
                record=record,
                mismatched_attributes=mismatches
            )

        return RegistryConsistencyResult(
            status=RegistryConsistencyStatus.REGISTRY_MATCH,
            message="CCTV visual attributes align with demonstration registry record.",
            record=record,
            mismatched_attributes=[]
        )
