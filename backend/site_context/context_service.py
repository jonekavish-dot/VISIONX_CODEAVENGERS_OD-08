"""
IVACS V-TRACE Site Context Service
Unifies permits, zones, and route integrity verification into a single service.
"""

import logging
from typing import Optional, Dict, Any
from backend.site_context.permits import PermitManager
from backend.site_context.route_rules import RouteIntegrityChecker
from backend.site_context.zones import CameraZoneManager
from backend.site_context.schemas import (
    PermitCheckResult,
    RouteCheckResult,
    PermitCheckStatus,
    RouteStatus
)

logger = logging.getLogger("vtrace.context_service")

class SiteContextService:
    """Unified service for site security access, camera zones, and route integrity."""

    def __init__(
        self,
        permit_manager: Optional[PermitManager] = None,
        route_checker: Optional[RouteIntegrityChecker] = None
    ):
        self.permit_manager = permit_manager or PermitManager()
        self.route_checker = route_checker or RouteIntegrityChecker()

    def evaluate_site_access(
        self,
        vehicle_id: str,
        plate: Optional[str],
        camera_id: str,
        zone: Optional[str] = None,
        timestamp: Optional[str] = None,
        is_demo: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluates both permit authorization and route sequence.
        Returns combined access assessment.
        """
        eval_zone = zone or CameraZoneManager.get_zone_for_camera(camera_id)
        eval_time = timestamp or datetime.now().isoformat()

        # 1. Permit evaluation
        permit_res = self.permit_manager.check_permit(plate, eval_zone)

        # 2. Route integrity evaluation
        route_res = self.route_checker.check_route(
            vehicle_id=vehicle_id,
            plate=plate,
            camera_id=camera_id,
            current_zone=eval_zone,
            timestamp_str=eval_time,
            is_demo=is_demo
        )

        return {
            "permit": permit_res,
            "route": route_res,
            "zone": eval_zone,
            "camera_id": camera_id
        }
