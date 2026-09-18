"""
IVACS V-TRACE Alerts & Trust Snapshot Module
Exports alert service, rules, and schemas.
"""

from backend.alerts.schemas import (
    AlertItem,
    AlertType,
    AlertSeverity,
    VehicleTrustSnapshot,
    DashboardSummary,
    LiveCameraCard
)
from backend.alerts.alert_rules import format_alert
from backend.alerts.alert_service import AlertService

__all__ = [
    "AlertItem",
    "AlertType",
    "AlertSeverity",
    "VehicleTrustSnapshot",
    "DashboardSummary",
    "LiveCameraCard",
    "format_alert",
    "AlertService"
]
