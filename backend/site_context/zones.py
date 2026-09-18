"""
IVACS V-TRACE Camera & Zone Mapping
Manages CCTV camera locations, security zones, and spatial configurations.
"""

from typing import Dict, List, Optional
from backend.config import CAMERAS, DEFAULT_CAMERA_ID
from backend.site_context.schemas import CameraZoneConfig
from backend.database.database import get_camera_zones

class CameraZoneManager:
    """Provides zone lookup and camera definitions."""

    @staticmethod
    def get_zone_for_camera(camera_id: str) -> str:
        if camera_id in CAMERAS:
            return CAMERAS[camera_id].zone
        return "UNKNOWN_ZONE"

    @staticmethod
    def get_all_camera_zones() -> List[CameraZoneConfig]:
        rows = get_camera_zones()
        if rows:
            return [CameraZoneConfig(**r) for r in rows]
        # Fallback to config
        return [
            CameraZoneConfig(
                camera_id=cfg.id,
                name=cfg.name,
                zone=cfg.zone,
                description=f"CCTV camera covering zone {cfg.zone}"
            )
            for cfg in CAMERAS.values()
        ]
