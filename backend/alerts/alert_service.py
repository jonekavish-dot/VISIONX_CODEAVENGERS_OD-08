"""
IVACS V-TRACE Alert Service & Unified Trust Engine
Manages alert generation, deduplication, persistence, and unified VehicleTrustSnapshot synthesis.
"""

import time
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from backend.alerts.schemas import (
    AlertItem,
    AlertType,
    AlertSeverity,
    VehicleTrustSnapshot,
    DashboardSummary
)
from backend.alerts.alert_rules import format_alert
from backend.database.database import (
    insert_alert,
    get_alerts as db_get_alerts,
    get_alert_by_id as db_get_alert_by_id,
    get_vehicle_identity_by_id,
    get_identity_observations_for_vehicle,
    get_vehicle_comparison,
    get_dashboard_summary_counts
)
from backend.vehicle_registry.registry_service import VehicleRegistryService
from backend.site_context.context_service import SiteContextService
from backend.site_context.schemas import PermitCheckStatus, RouteStatus

logger = logging.getLogger("vtrace.alert_service")

class AlertService:
    """Central engine for managing operational security alerts and unified trust snapshots."""

    def __init__(
        self,
        registry_service: Optional[VehicleRegistryService] = None,
        context_service: Optional[SiteContextService] = None,
        cooldown_seconds: int = 10
    ):
        self.registry_service = registry_service or VehicleRegistryService()
        self.context_service = context_service or SiteContextService()
        self.cooldown_seconds = cooldown_seconds
        # Cooldown cache: (vehicle_id, alert_type) -> timestamp
        self._cooldown_cache: Dict[Tuple[Optional[str], str], float] = {}

    def clear_cooldown(self):
        self._cooldown_cache.clear()

    def create_alert(
        self,
        alert_type: str,
        camera_id: str,
        zone: str,
        plate: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        similarity: float = 0.0,
        details: str = "",
        evidence_references: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
        is_demo: bool = False
    ) -> Optional[AlertItem]:
        """
        Creates an alert using deterministic templates with temporal deduplication.
        Returns AlertItem if created, or None if suppressed by cooldown.
        """
        now_ts = time.time()
        dedup_key = (vehicle_id or plate, alert_type)
        last_ts = self._cooldown_cache.get(dedup_key, 0.0)

        if (now_ts - last_ts) < self.cooldown_seconds:
            logger.debug(f"Alert '{alert_type}' for {dedup_key} suppressed by cooldown.")
            return None

        self._cooldown_cache[dedup_key] = now_ts
        iso_time = timestamp or datetime.now().isoformat()

        formatted = format_alert(
            alert_type=alert_type,
            plate=plate or "UNKNOWN",
            similarity=similarity,
            vehicle_id=vehicle_id or "UNKNOWN",
            camera_id=camera_id,
            zone=zone,
            details=details
        )

        alert_id = insert_alert(
            alert_type=alert_type,
            severity=formatted["severity"],
            vehicle_id=vehicle_id,
            plate=plate,
            camera_id=camera_id,
            zone=zone,
            timestamp=iso_time,
            title=formatted["title"],
            reason=formatted["reason"],
            action_required=formatted["action_required"],
            requires_manual_review=formatted["requires_manual_review"],
            evidence_references=evidence_references,
            is_demo=is_demo
        )

        return AlertItem(
            id=alert_id,
            type=alert_type,
            severity=formatted["severity"],
            vehicle_id=vehicle_id,
            plate=plate,
            camera_id=camera_id,
            zone=zone,
            timestamp=iso_time,
            title=formatted["title"],
            reason=formatted["reason"],
            action_required=formatted["action_required"],
            requires_manual_review=formatted["requires_manual_review"],
            evidence_references=evidence_references or {},
            review_status="PENDING",
            is_demo=is_demo
        )

    def get_alerts(
        self,
        limit: int = 50,
        offset: int = 0,
        plate: Optional[str] = None,
        camera_id: Optional[str] = None,
        zone: Optional[str] = None,
        alert_type: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[AlertItem]:
        rows = db_get_alerts(
            limit=limit,
            offset=offset,
            plate=plate,
            camera_id=camera_id,
            zone=zone,
            alert_type=alert_type,
            severity=severity
        )
        return [
            AlertItem(
                id=r["id"],
                type=r["alert_type"],
                severity=r["severity"],
                vehicle_id=r["vehicle_id"],
                plate=r["plate"],
                camera_id=r["camera_id"],
                zone=r["zone"],
                timestamp=r["timestamp"],
                title=r["title"],
                reason=r["reason"],
                action_required=r["action_required"],
                requires_manual_review=r["requires_manual_review"],
                evidence_references=r.get("evidence_references", {}),
                review_status=r.get("review_status", "PENDING"),
                is_demo=bool(r.get("is_demo", 0))
            )
            for r in rows
        ]

    def get_alert_by_id(self, alert_id: int) -> Optional[AlertItem]:
        r = db_get_alert_by_id(alert_id)
        if not r:
            return None
        return AlertItem(
            id=r["id"],
            type=r["alert_type"],
            severity=r["severity"],
            vehicle_id=r["vehicle_id"],
            plate=r["plate"],
            camera_id=r["camera_id"],
            zone=r["zone"],
            timestamp=r["timestamp"],
            title=r["title"],
            reason=r["reason"],
            action_required=r["action_required"],
            requires_manual_review=r["requires_manual_review"],
            evidence_references=r.get("evidence_references", {}),
            review_status=r.get("review_status", "PENDING"),
            is_demo=bool(r.get("is_demo", 0))
        )

    def get_trust_snapshot(self, vehicle_id: str) -> Optional[VehicleTrustSnapshot]:
        """
        Synthesizes a unified, explainable VehicleTrustSnapshot for a vehicle.
        Combines: OCR plate, visual identity, registry, permit, zone, route, and historical observations.
        """
        v_rec = get_vehicle_identity_by_id(vehicle_id)
        obs_list = get_identity_observations_for_vehicle(vehicle_id)

        if not v_rec and not obs_list:
            return None

        current_obs = obs_list[0] if obs_list else None
        plate = (current_obs.observed_plate if current_obs else None) or (v_rec.canonical_plate if v_rec else None)
        v_class = v_rec.vehicle_class if v_rec else "car"
        camera_id = current_obs.camera_id if current_obs else "CAM-01"
        zone = current_obs.zone if current_obs else "GATE_IN"
        timestamp = current_obs.timestamp if current_obs else datetime.now().isoformat()
        id_event = current_obs.event_type.value if current_obs else "NEW_VEHICLE"
        sim_val = current_obs.visual_similarity if current_obs else 1.0

        # 1. Check Registry Consistency
        reg_res = self.registry_service.check_consistency(plate, v_class)
        registry_status = reg_res.status.value

        # 2. Check Site Permit
        permit_res = self.context_service.permit_manager.check_permit(plate, zone)
        permit_status = permit_res.status.value
        zone_status = "AUTHORIZED" if permit_res.status == PermitCheckStatus.AUTHORIZED else "UNAUTHORIZED_ZONE"

        # 3. Check Route Status
        recent_transits = self.context_service.route_checker.check_route(
            vehicle_id=vehicle_id,
            plate=plate,
            camera_id=camera_id,
            current_zone=zone,
            timestamp_str=timestamp,
            is_demo=True
        )
        route_status = recent_transits.status.value

        # 4. Synthesize Overall Event & Review Requirement
        requires_review = False
        overall_event = "NORMAL"

        if id_event in ["POSSIBLE_IDENTITY_MISMATCH", "POSSIBLE_PLATE_SWAP"]:
            overall_event = "IDENTITY_INCONSISTENCY"
            requires_review = True
        elif registry_status == "REGISTRY_ATTRIBUTE_MISMATCH":
            overall_event = "REGISTRY_MISMATCH"
            requires_review = True
        elif permit_status in ["PERMIT_EXPIRED", "UNAUTHORIZED_ZONE"]:
            overall_event = "PERMIT_VIOLATION"
            requires_review = True
        elif route_status == "ROUTE_INTEGRITY_ANOMALY":
            overall_event = "ROUTE_ANOMALY"
            requires_review = True
        elif id_event == "PLATE_UNREADABLE_VEHICLE_MATCH":
            overall_event = "CONTINUOUS_VISUAL_TRACK"
            requires_review = False

        # Gather evidence references
        evidence = None
        comp = get_vehicle_comparison(vehicle_id)
        if comp:
            evidence = comp.model_dump()

        return VehicleTrustSnapshot(
            vehicle_id=vehicle_id,
            plate=plate,
            vehicle_class=v_class,
            camera_id=camera_id,
            zone=zone,
            timestamp=timestamp,
            identity_event=id_event,
            visual_similarity=sim_val,
            registry_status=registry_status,
            permit_status=permit_status,
            zone_status=zone_status,
            route_status=route_status,
            overall_event=overall_event,
            requires_review=requires_review,
            evidence=evidence
        )

    def get_dashboard_summary(self) -> DashboardSummary:
        counts = get_dashboard_summary_counts()
        return DashboardSummary(**counts)
