"""
IVACS V-TRACE Site Permit Enforcement Engine
Validates vehicle license plates against authorized construction-site permits.
"""

import logging
from datetime import datetime
from typing import Optional, List
from backend.site_context.schemas import (
    SitePermit,
    PermitCheckStatus,
    PermitCheckResult
)
from backend.database.database import get_permits_for_plate

logger = logging.getLogger("vtrace.permits")

class PermitManager:
    """Evaluates access authorization based on site permit manifest."""

    def check_permit(self, plate: Optional[str], current_zone: str) -> PermitCheckResult:
        if not plate:
            return PermitCheckResult(
                status=PermitCheckStatus.UNKNOWN_VEHICLE,
                reason="Plate unreadable; cannot verify permit.",
                allowed_zones=[],
                current_zone=current_zone
            )

        clean_plate = plate.strip().upper().replace(" ", "").replace("-", "")
        permits_data = get_permits_for_plate(clean_plate)

        if not permits_data:
            return PermitCheckResult(
                status=PermitCheckStatus.NO_SITE_PERMIT,
                reason=f"No site access permit registered for plate '{clean_plate}'.",
                allowed_zones=[],
                current_zone=current_zone
            )

        # Evaluate most relevant permit
        now_dt = datetime.now()
        active_permit: Optional[SitePermit] = None

        for p_row in permits_data:
            permit_obj = SitePermit(
                id=p_row.get("id"),
                plate=p_row.get("plate", clean_plate),
                site_id=p_row.get("site_id", "SITE-BLR-01"),
                allowed_zones=p_row.get("allowed_zones", []),
                valid_from=p_row.get("valid_from", ""),
                valid_until=p_row.get("valid_until", ""),
                purpose=p_row.get("purpose", ""),
                status=p_row.get("status", "ACTIVE"),
                is_demo=bool(p_row.get("is_demo", 1))
            )

            # Check explicit status
            if permit_obj.status.upper() == "EXPIRED":
                return PermitCheckResult(
                    status=PermitCheckStatus.PERMIT_EXPIRED,
                    permit=permit_obj,
                    reason=f"Site permit for '{clean_plate}' is marked EXPIRED (Valid until: {permit_obj.valid_until}).",
                    allowed_zones=permit_obj.allowed_zones,
                    current_zone=current_zone
                )

            # Check date boundary if parseable
            try:
                valid_until_dt = datetime.fromisoformat(permit_obj.valid_until)
                if now_dt > valid_until_dt:
                    return PermitCheckResult(
                        status=PermitCheckStatus.PERMIT_EXPIRED,
                        permit=permit_obj,
                        reason=f"Site permit expired on {permit_obj.valid_until}.",
                        allowed_zones=permit_obj.allowed_zones,
                        current_zone=current_zone
                    )
            except Exception:
                # String comparison fallback for YYYY-MM-DD
                if len(permit_obj.valid_until) >= 10 and now_dt.strftime("%Y-%m-%d") > permit_obj.valid_until[:10]:
                    return PermitCheckResult(
                        status=PermitCheckStatus.PERMIT_EXPIRED,
                        permit=permit_obj,
                        reason=f"Site permit expired on {permit_obj.valid_until}.",
                        allowed_zones=permit_obj.allowed_zones,
                        current_zone=current_zone
                    )

            active_permit = permit_obj
            break

        if not active_permit:
            return PermitCheckResult(
                status=PermitCheckStatus.NO_SITE_PERMIT,
                reason=f"No valid permit found for plate '{clean_plate}'.",
                allowed_zones=[],
                current_zone=current_zone
            )

        # Check zone authorization
        if current_zone not in active_permit.allowed_zones:
            return PermitCheckResult(
                status=PermitCheckStatus.UNAUTHORIZED_ZONE,
                permit=active_permit,
                reason=f"Vehicle '{clean_plate}' is not authorized to enter '{current_zone}'. Allowed: {active_permit.allowed_zones}.",
                allowed_zones=active_permit.allowed_zones,
                current_zone=current_zone
            )

        return PermitCheckResult(
            status=PermitCheckStatus.AUTHORIZED,
            permit=active_permit,
            reason=f"Access authorized for zone '{current_zone}' under permit {active_permit.site_id}.",
            allowed_zones=active_permit.allowed_zones,
            current_zone=current_zone
        )
