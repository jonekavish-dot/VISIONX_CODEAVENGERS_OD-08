"""
IVACS V-TRACE Alert Rules & Templates
Deterministic, human-authored notification templates for site security and identity anomalies.
Zero Generative AI / LLM at runtime.
"""

from typing import Dict, Any
from backend.alerts.schemas import AlertType, AlertSeverity

ALERT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    AlertType.POSSIBLE_IDENTITY_MISMATCH.value: {
        "title": "POSSIBLE PLATE–VEHICLE IDENTITY MISMATCH",
        "severity": AlertSeverity.CRITICAL.value,
        "reason_template": "Observed plate {plate} is associated with a vehicle appearance that deviates from the historical profile (similarity: {similarity:.2f}). Possible plate cloning.",
        "action_required": "Manual verification required. Security checkpoint must inspect vehicle physically.",
        "requires_manual_review": True
    },
    AlertType.POSSIBLE_PLATE_SWAP.value: {
        "title": "POSSIBLE LICENSE PLATE SWAP DETECTED",
        "severity": AlertSeverity.CRITICAL.value,
        "reason_template": "Vehicle visual fingerprint matches previously registered identity bearing a different plate (similarity: {similarity:.2f}). Possible plate swap anomaly.",
        "action_required": "Inspect vehicle VIN and cross-verify with site vehicle pass.",
        "requires_manual_review": True
    },
    AlertType.PLATE_UNREADABLE_VEHICLE_MATCH.value: {
        "title": "UNREADABLE PLATE TRACKED VIA VISUAL FINGERPRINT",
        "severity": AlertSeverity.INFO.value,
        "reason_template": "Plate unreadable or obscured on camera {camera_id}, but vehicle visual appearance matches known identity {vehicle_id} (similarity: {similarity:.2f}).",
        "action_required": "Inform gate staff to inspect dirty/obscured plate on departure.",
        "requires_manual_review": False
    },
    AlertType.REGISTRY_ATTRIBUTE_MISMATCH.value: {
        "title": "REGISTRY ATTRIBUTE MISMATCH",
        "severity": AlertSeverity.WARNING.value,
        "reason_template": "Observed vehicle visual attributes deviate from demonstration registry record: {details}.",
        "action_required": "Cross-check physical vehicle type with registration documents.",
        "requires_manual_review": True
    },
    AlertType.PERMIT_EXPIRED.value: {
        "title": "SITE ACCESS PERMIT EXPIRED",
        "severity": AlertSeverity.WARNING.value,
        "reason_template": "Site access permit for vehicle '{plate}' has expired: {details}.",
        "action_required": "Redirect vehicle to site registration office for permit renewal.",
        "requires_manual_review": True
    },
    AlertType.UNAUTHORIZED_ZONE.value: {
        "title": "UNAUTHORIZED ZONE ENTRY",
        "severity": AlertSeverity.CRITICAL.value,
        "reason_template": "Vehicle '{plate}' detected in zone '{zone}', which is not authorized under current permit manifest.",
        "action_required": "Security intercept required. Escort vehicle to designated authorized zone.",
        "requires_manual_review": True
    },
    AlertType.ROUTE_INTEGRITY_ANOMALY.value: {
        "title": "ROUTE INTEGRITY ANOMALY",
        "severity": AlertSeverity.CRITICAL.value,
        "reason_template": "{details}",
        "action_required": "Verify vehicle checkpoint logs and CCTV route timeline.",
        "requires_manual_review": True
    },
    AlertType.UNKNOWN_VEHICLE.value: {
        "title": "UNREGISTERED VEHICLE AT SITE CHECKPOINT",
        "severity": AlertSeverity.WARNING.value,
        "reason_template": "Vehicle with plate '{plate}' has no valid registration or permit on file.",
        "action_required": "Issue temporary contractor visitor pass before allowing entry.",
        "requires_manual_review": True
    }
}

def format_alert(
    alert_type: str,
    plate: str = "UNKNOWN",
    similarity: float = 0.0,
    vehicle_id: str = "UNKNOWN",
    camera_id: str = "CAM-01",
    zone: str = "GATE_IN",
    details: str = ""
) -> Dict[str, Any]:
    """Generates structured, human-authored alert details without calling an LLM."""
    tpl = ALERT_TEMPLATES.get(alert_type, {
        "title": "OPERATIONAL SECURITY NOTICE",
        "severity": AlertSeverity.INFO.value,
        "reason_template": "Analytical notice regarding vehicle {plate} in zone {zone}: {details}.",
        "action_required": "Standard site operational review.",
        "requires_manual_review": False
    })

    reason = tpl["reason_template"].format(
        plate=plate or "UNKNOWN",
        similarity=similarity or 0.0,
        vehicle_id=vehicle_id or "UNKNOWN",
        camera_id=camera_id or "CAM-01",
        zone=zone or "GATE_IN",
        details=details or ""
    )

    return {
        "title": tpl["title"],
        "severity": tpl["severity"],
        "reason": reason,
        "action_required": tpl["action_required"],
        "requires_manual_review": tpl["requires_manual_review"]
    }
