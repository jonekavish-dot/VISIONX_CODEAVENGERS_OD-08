"""
IVACS V-TRACE Route Integrity Engine
Deterministic verification of site route sequences and travel times.
Zero Generative AI / LLM at runtime.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from backend.site_context.schemas import RouteCheckResult, RouteStatus, RouteRule
from backend.database.database import (
    get_route_rules,
    record_vehicle_transit,
    get_recent_transit_for_vehicle
)

logger = logging.getLogger("vtrace.route_rules")

class RouteIntegrityChecker:
    """Detects impossible transitions and impossible travel times across camera zones."""

    def __init__(self):
        self._rules_cache: List[RouteRule] = []
        self._refresh_rules()

    def _refresh_rules(self):
        rows = get_route_rules()
        self._rules_cache = [RouteRule(**r) for r in rows]

    def check_route(
        self,
        vehicle_id: str,
        plate: Optional[str],
        camera_id: str,
        current_zone: str,
        timestamp_str: str,
        is_demo: bool = True
    ) -> RouteCheckResult:
        """
        Validates vehicle transition from its previous recorded zone to current_zone.
        Records the new sighting in transit history.
        """
        recent = get_recent_transit_for_vehicle(vehicle_id, limit=1)

        # First observation for this vehicle is always normal baseline
        if not recent:
            record_vehicle_transit(
                vehicle_id=vehicle_id,
                plate=plate,
                camera_id=camera_id,
                zone=current_zone,
                timestamp=timestamp_str,
                is_demo=is_demo
            )
            return RouteCheckResult(
                status=RouteStatus.NORMAL,
                is_anomaly=False,
                reason=f"Initial sighting at {current_zone}.",
                previous_zone=None,
                current_zone=current_zone,
                elapsed_seconds=None
            )

        prev_transit = recent[0]
        prev_zone = prev_transit["zone"]
        prev_time_str = prev_transit["timestamp"]

        # Same zone is normal continuous observation
        if prev_zone == current_zone:
            return RouteCheckResult(
                status=RouteStatus.NORMAL,
                is_anomaly=False,
                reason=f"Continuous observation in zone {current_zone}.",
                previous_zone=prev_zone,
                current_zone=current_zone,
                elapsed_seconds=0.0
            )

        # Compute elapsed travel time
        elapsed_seconds: Optional[float] = None
        try:
            prev_dt = datetime.fromisoformat(prev_time_str)
            curr_dt = datetime.fromisoformat(timestamp_str)
            elapsed_seconds = max(0.0, (curr_dt - prev_dt).total_seconds())
        except Exception:
            elapsed_seconds = 1.0

        # Disallowed transition check: e.g. GATE_OUT -> MATERIAL_YARD or GATE_OUT -> ACTIVE_ZONE
        if prev_zone == "GATE_OUT" and current_zone in ["MATERIAL_YARD", "ACTIVE_ZONE"]:
            # Record transit
            record_vehicle_transit(
                vehicle_id=vehicle_id,
                plate=plate,
                camera_id=camera_id,
                zone=current_zone,
                timestamp=timestamp_str,
                is_demo=is_demo
            )
            return RouteCheckResult(
                status=RouteStatus.ROUTE_INTEGRITY_ANOMALY,
                is_anomaly=True,
                reason=f"Impossible route transition: Vehicle moved backward from {prev_zone} into {current_zone}.",
                previous_zone=prev_zone,
                current_zone=current_zone,
                elapsed_seconds=elapsed_seconds
            )

        # Check configured travel rules
        matched_rule: Optional[RouteRule] = None
        for rule in self._rules_cache:
            if rule.from_zone == prev_zone and rule.to_zone == current_zone:
                matched_rule = rule
                break

        # Record this transit sighting
        record_vehicle_transit(
            vehicle_id=vehicle_id,
            plate=plate,
            camera_id=camera_id,
            zone=current_zone,
            timestamp=timestamp_str,
            is_demo=is_demo
        )

        if matched_rule:
            if elapsed_seconds is not None and elapsed_seconds < matched_rule.minimum_travel_seconds:
                return RouteCheckResult(
                    status=RouteStatus.ROUTE_INTEGRITY_ANOMALY,
                    is_anomaly=True,
                    reason=f"Impossible travel speed: Traveled from {prev_zone} to {current_zone} in {elapsed_seconds:.1f}s (configured minimum: {matched_rule.minimum_travel_seconds}s).",
                    previous_zone=prev_zone,
                    current_zone=current_zone,
                    elapsed_seconds=elapsed_seconds,
                    min_expected_seconds=matched_rule.minimum_travel_seconds
                )
            return RouteCheckResult(
                status=RouteStatus.NORMAL,
                is_anomaly=False,
                reason=f"Valid route transition from {prev_zone} to {current_zone} ({elapsed_seconds:.1f}s elapsed).",
                previous_zone=prev_zone,
                current_zone=current_zone,
                elapsed_seconds=elapsed_seconds,
                min_expected_seconds=matched_rule.minimum_travel_seconds
            )

        # Unconfigured / jump transition (e.g. directly skipping critical checkpoints)
        if prev_zone == "GATE_IN" and current_zone == "GATE_OUT":
            return RouteCheckResult(
                status=RouteStatus.ROUTE_INTEGRITY_ANOMALY,
                is_anomaly=True,
                reason=f"Suspicious transit: Vehicle bypassed inner inspection zones directly from {prev_zone} to {current_zone}.",
                previous_zone=prev_zone,
                current_zone=current_zone,
                elapsed_seconds=elapsed_seconds
            )

        return RouteCheckResult(
            status=RouteStatus.NORMAL,
            is_anomaly=False,
            reason=f"Route transit from {prev_zone} to {current_zone} recorded.",
            previous_zone=prev_zone,
            current_zone=current_zone,
            elapsed_seconds=elapsed_seconds
        )
