"""
IVACS V-TRACE Database Access Layer
Uses standard SQLite3 for zero-overhead, reliable, hackathon-ready persistence.
Handles detections, persistent vehicle identities, and identity observations.
"""

import os
import sqlite3
import json
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime
from backend.config import DB_PATH
from backend.schemas.detection import DetectionEvent, ProcessingStatus

if TYPE_CHECKING:
    from backend.vehicle_identity.schemas import VehicleIdentity, IdentityObservation, IdentityEventType

def get_connection():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Existing Detections Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        camera_id TEXT NOT NULL,
        zone TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        frame_number INTEGER NOT NULL,
        status TEXT NOT NULL,
        vehicle_class TEXT,
        vehicle_confidence REAL,
        plate TEXT,
        raw_plate TEXT,
        plate_confidence REAL,
        ocr_confidence REAL,
        vehicle_bbox TEXT,
        plate_bbox TEXT,
        vehicle_crop_path TEXT,
        plate_crop_path TEXT,
        frame_path TEXT,
        annotated_frame_path TEXT,
        vehicle_id TEXT,
        visual_similarity REAL,
        identity_event TEXT,
        identity_match_status TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # Non-breaking migration: add columns if they were not present in earlier schema
    existing_cols = [r[1] for r in cursor.execute("PRAGMA table_info(detections)").fetchall()]
    for col_name, col_type in [
        ("vehicle_id", "TEXT"),
        ("visual_similarity", "REAL"),
        ("identity_event", "TEXT"),
        ("identity_match_status", "TEXT"),
        ("is_demo", "INTEGER DEFAULT 0")
    ]:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE detections ADD COLUMN {col_name} {col_type}")
    
    # 2. Vehicle Identities Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicle_identities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id TEXT UNIQUE NOT NULL,
        canonical_plate TEXT,
        first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL,
        visit_count INTEGER NOT NULL DEFAULT 1,
        vehicle_class TEXT,
        color TEXT,
        embedding_json TEXT NOT NULL,
        is_demo INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)
    veh_cols = [r[1] for r in cursor.execute("PRAGMA table_info(vehicle_identities)").fetchall()]
    if "is_demo" not in veh_cols:
        cursor.execute("ALTER TABLE vehicle_identities ADD COLUMN is_demo INTEGER DEFAULT 0")

    # 3. Identity Observations Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS identity_observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_identity_id TEXT NOT NULL,
        observed_plate TEXT,
        plate_confidence REAL,
        ocr_confidence REAL,
        visual_similarity REAL,
        event_type TEXT NOT NULL,
        camera_id TEXT NOT NULL,
        zone TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        frame_number INTEGER NOT NULL,
        vehicle_crop_path TEXT,
        plate_crop_path TEXT,
        frame_path TEXT,
        previous_crop_path TEXT,
        is_demo INTEGER DEFAULT 0
    )
    """)
    obs_cols = [r[1] for r in cursor.execute("PRAGMA table_info(identity_observations)").fetchall()]
    if "is_demo" not in obs_cols:
        cursor.execute("ALTER TABLE identity_observations ADD COLUMN is_demo INTEGER DEFAULT 0")

    conn.commit()
    conn.close()

# ==================== DETECTIONS TABLE OPERATIONS ====================

def insert_detection(event: DetectionEvent) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    
    vehicle_bbox_json = json.dumps(event.vehicle_bbox) if event.vehicle_bbox is not None else None
    plate_bbox_json = json.dumps(event.plate_bbox) if event.plate_bbox is not None else None
    
    cursor.execute("""
    INSERT INTO detections (
        camera_id, zone, timestamp, frame_number, status,
        vehicle_class, vehicle_confidence, plate, raw_plate,
        plate_confidence, ocr_confidence, vehicle_bbox, plate_bbox,
        vehicle_crop_path, plate_crop_path, frame_path, annotated_frame_path,
        vehicle_id, visual_similarity, identity_event, identity_match_status, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event.camera_id,
        event.zone,
        event.timestamp,
        event.frame_number,
        event.status.value if isinstance(event.status, ProcessingStatus) else str(event.status),
        event.vehicle_class,
        event.vehicle_confidence,
        event.plate,
        event.raw_plate,
        event.plate_confidence,
        event.ocr_confidence,
        vehicle_bbox_json,
        plate_bbox_json,
        event.vehicle_crop_path,
        event.plate_crop_path,
        event.frame_path,
        event.annotated_frame_path,
        event.vehicle_id,
        event.visual_similarity,
        event.identity_event,
        event.identity_match_status,
        event.created_at or datetime.now().isoformat()
    ))
    conn.commit()
    inserted_id = cursor.lastrowid
    conn.close()
    return inserted_id

def row_to_event(row: sqlite3.Row) -> DetectionEvent:
    vehicle_bbox = json.loads(row["vehicle_bbox"]) if row["vehicle_bbox"] else None
    plate_bbox = json.loads(row["plate_bbox"]) if row["plate_bbox"] else None
    
    status_str = row["status"]
    try:
        status_enum = ProcessingStatus(status_str)
    except ValueError:
        status_enum = ProcessingStatus.DETECTED

    keys = row.keys()
    vehicle_id = row["vehicle_id"] if "vehicle_id" in keys else None
    visual_similarity = row["visual_similarity"] if "visual_similarity" in keys else None
    identity_event = row["identity_event"] if "identity_event" in keys else None
    identity_match_status = row["identity_match_status"] if "identity_match_status" in keys else None
        
    return DetectionEvent(
        id=row["id"],
        camera_id=row["camera_id"],
        zone=row["zone"],
        timestamp=row["timestamp"],
        frame_number=row["frame_number"],
        status=status_enum,
        vehicle_class=row["vehicle_class"],
        vehicle_confidence=row["vehicle_confidence"],
        plate=row["plate"],
        raw_plate=row["raw_plate"],
        plate_confidence=row["plate_confidence"],
        ocr_confidence=row["ocr_confidence"],
        vehicle_bbox=vehicle_bbox,
        plate_bbox=plate_bbox,
        vehicle_crop_path=row["vehicle_crop_path"],
        plate_crop_path=row["plate_crop_path"],
        frame_path=row["frame_path"],
        annotated_frame_path=row["annotated_frame_path"],
        vehicle_id=vehicle_id,
        visual_similarity=visual_similarity,
        identity_event=identity_event,
        identity_match_status=identity_match_status,
        created_at=row["created_at"]
    )

def get_all_detections(limit: int = 100, offset: int = 0) -> List[DetectionEvent]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM detections 
        ORDER BY id DESC 
        LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    return [row_to_event(r) for r in rows]

def get_latest_detection() -> Optional[DetectionEvent]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM detections 
        ORDER BY id DESC 
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    if row:
        return row_to_event(row)
    return None

def get_total_detections_count() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM detections")
    count = cursor.fetchone()[0]
    conn.close()
    return count

# ==================== VEHICLE IDENTITIES OPERATIONS ====================

def get_next_vehicle_id() -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT vehicle_id FROM vehicle_identities")
    rows = cursor.fetchall()
    conn.close()
    max_num = 0
    for r in rows:
        vid_str = r["vehicle_id"]
        if vid_str and vid_str.startswith("V-"):
            try:
                num = int(vid_str.split("-")[1])
                if num > max_num:
                    max_num = num
            except (ValueError, IndexError):
                pass
    return f"V-{max_num + 1:03d}"

def insert_vehicle_identity(identity: "VehicleIdentity", is_demo: bool = False) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    emb_json = json.dumps(identity.embedding) if identity.embedding else "[]"
    demo_flag = 1 if (is_demo or getattr(identity, 'is_demo', False)) else 0
    cursor.execute("""
    INSERT INTO vehicle_identities (
        vehicle_id, canonical_plate, first_seen, last_seen, visit_count,
        vehicle_class, color, embedding_json, is_demo, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        identity.vehicle_id,
        identity.canonical_plate,
        identity.first_seen,
        identity.last_seen,
        identity.visit_count,
        identity.vehicle_class,
        identity.color,
        emb_json,
        demo_flag,
        identity.created_at,
        identity.updated_at
    ))
    conn.commit()
    inserted_id = cursor.lastrowid
    conn.close()
    return inserted_id

def update_vehicle_identity(
    vehicle_id: str,
    last_seen: str,
    visit_count: int,
    canonical_plate: Optional[str] = None,
    embedding: Optional[List[float]] = None
):
    conn = get_connection()
    cursor = conn.cursor()
    
    fields = ["last_seen = ?", "visit_count = ?", "updated_at = ?"]
    params = [last_seen, visit_count, datetime.now().isoformat()]
    
    if canonical_plate:
        fields.append("canonical_plate = ?")
        params.append(canonical_plate)
    if embedding:
        fields.append("embedding_json = ?")
        params.append(json.dumps(embedding))
        
    params.append(vehicle_id)
    query = f"UPDATE vehicle_identities SET {', '.join(fields)} WHERE vehicle_id = ?"
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def row_to_vehicle_identity(row: sqlite3.Row) -> "VehicleIdentity":
    from backend.vehicle_identity.schemas import VehicleIdentity
    emb = json.loads(row["embedding_json"]) if row["embedding_json"] else []
    is_demo_val = bool(row["is_demo"]) if "is_demo" in row.keys() else False
    return VehicleIdentity(
        id=row["id"],
        vehicle_id=row["vehicle_id"],
        canonical_plate=row["canonical_plate"],
        first_seen=row["first_seen"],
        last_seen=row["last_seen"],
        visit_count=row["visit_count"],
        vehicle_class=row["vehicle_class"],
        color=row["color"],
        embedding=emb,
        is_demo=is_demo_val,
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )

def get_vehicle_identity_by_id(vehicle_id: str) -> Optional["VehicleIdentity"]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicle_identities WHERE vehicle_id = ?", (vehicle_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row_to_vehicle_identity(row)
    return None

def get_vehicle_identity_by_plate(plate: str) -> Optional["VehicleIdentity"]:
    if not plate:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicle_identities WHERE canonical_plate = ? ORDER BY visit_count DESC LIMIT 1", (plate.strip().upper(),))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row_to_vehicle_identity(row)
    return None

def get_all_vehicle_identities() -> List["VehicleIdentity"]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicle_identities ORDER BY last_seen DESC")
    rows = cursor.fetchall()
    conn.close()
    return [row_to_vehicle_identity(r) for r in rows]

# ==================== IDENTITY OBSERVATIONS OPERATIONS ====================

def insert_identity_observation(obs: "IdentityObservation", is_demo: bool = False) -> int:
    from backend.vehicle_identity.schemas import IdentityEventType
    conn = get_connection()
    cursor = conn.cursor()
    demo_flag = 1 if (is_demo or getattr(obs, 'is_demo', False)) else 0
    cursor.execute("""
    INSERT INTO identity_observations (
        vehicle_identity_id, observed_plate, plate_confidence, ocr_confidence,
        visual_similarity, event_type, camera_id, zone, timestamp,
        frame_number, vehicle_crop_path, plate_crop_path, frame_path, previous_crop_path, is_demo
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        obs.vehicle_identity_id,
        obs.observed_plate,
        obs.plate_confidence,
        obs.ocr_confidence,
        obs.visual_similarity,
        obs.event_type.value if isinstance(obs.event_type, IdentityEventType) else str(obs.event_type),
        obs.camera_id,
        obs.zone,
        obs.timestamp,
        obs.frame_number,
        obs.vehicle_crop_path,
        obs.plate_crop_path,
        obs.frame_path,
        obs.previous_crop_path,
        demo_flag
    ))
    conn.commit()
    inserted_id = cursor.lastrowid
    conn.close()
    return inserted_id

def row_to_observation(row: sqlite3.Row) -> "IdentityObservation":
    from backend.vehicle_identity.schemas import IdentityObservation, IdentityEventType
    try:
        e_type = IdentityEventType(row["event_type"])
    except ValueError:
        e_type = IdentityEventType.NEW_VEHICLE
    is_demo_val = bool(row["is_demo"]) if "is_demo" in row.keys() else False
    return IdentityObservation(
        id=row["id"],
        vehicle_identity_id=row["vehicle_identity_id"],
        observed_plate=row["observed_plate"],
        plate_confidence=row["plate_confidence"],
        ocr_confidence=row["ocr_confidence"],
        visual_similarity=row["visual_similarity"],
        event_type=e_type,
        camera_id=row["camera_id"],
        zone=row["zone"],
        timestamp=row["timestamp"],
        frame_number=row["frame_number"],
        vehicle_crop_path=row["vehicle_crop_path"],
        plate_crop_path=row["plate_crop_path"],
        frame_path=row["frame_path"],
        previous_crop_path=row["previous_crop_path"],
        is_demo=is_demo_val
    )

def get_identity_observation_by_id(obs_id: int) -> Optional["IdentityObservation"]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM identity_observations WHERE id = ?", (obs_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row_to_observation(row)
    return None

def get_identity_observations_for_vehicle(vehicle_id: str) -> List["IdentityObservation"]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM identity_observations 
        WHERE vehicle_identity_id = ? 
        ORDER BY id DESC
    """, (vehicle_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row_to_observation(r) for r in rows]

def get_all_identity_observations(limit: int = 50, offset: int = 0) -> List["IdentityObservation"]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM identity_observations 
        ORDER BY id DESC 
        LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    return [row_to_observation(r) for r in rows]

def get_latest_identity_observation() -> Optional["IdentityObservation"]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM identity_observations 
        ORDER BY id DESC 
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    if row:
        return row_to_observation(row)
    return None

def get_vehicle_comparison(vehicle_id: str) -> Optional[Any]:
    from backend.vehicle_identity.schemas import (
        VehicleComparisonResponse,
        IdentityEventType,
        get_alert_text
    )
    v_record = get_vehicle_identity_by_id(vehicle_id)
    obs_list = get_identity_observations_for_vehicle(vehicle_id)
    if not obs_list:
        return None
    
    current_obs = obs_list[0]
    historical_obs = obs_list[1] if len(obs_list) > 1 else None

    alert_info = get_alert_text(current_obs.event_type, current_obs.observed_plate)

    hist_vehicle_img = current_obs.previous_crop_path
    hist_plate_img = None
    hist_plate = None
    hist_timestamp = None

    if historical_obs:
        if not hist_vehicle_img:
            hist_vehicle_img = historical_obs.vehicle_crop_path
        hist_plate_img = historical_obs.plate_crop_path
        hist_plate = historical_obs.observed_plate
        hist_timestamp = historical_obs.timestamp
    elif current_obs.event_type in [IdentityEventType.POSSIBLE_IDENTITY_MISMATCH, IdentityEventType.POSSIBLE_PLATE_SWAP]:
        # Cross-reference with candidate identity sharing same plate or appearance
        if current_obs.observed_plate:
            base_cand = get_vehicle_identity_by_plate(current_obs.observed_plate)
            if base_cand and base_cand.vehicle_id != vehicle_id:
                base_obs = get_identity_observations_for_vehicle(base_cand.vehicle_id)
                if base_obs:
                    hist_cand = base_obs[0]
                    if not hist_vehicle_img:
                        hist_vehicle_img = hist_cand.vehicle_crop_path
                    hist_plate_img = hist_cand.plate_crop_path
                    hist_plate = hist_cand.observed_plate or base_cand.canonical_plate
                    hist_timestamp = hist_cand.timestamp

    if not hist_plate:
        hist_plate = v_record.canonical_plate if v_record else current_obs.observed_plate

    # Sibling plate image fallback for comparative review
    if not hist_plate_img and hist_vehicle_img:
        cand_plate_path = hist_vehicle_img.replace("_vehicle.jpg", "_plate.jpg")
        if os.path.exists(cand_plate_path):
            hist_plate_img = cand_plate_path

    sim_val = current_obs.visual_similarity if current_obs.visual_similarity is not None else 0.0

    return VehicleComparisonResponse(
        vehicle_id=vehicle_id,
        observed_plate=current_obs.observed_plate,
        historical_plate=hist_plate,
        current_vehicle_image=current_obs.vehicle_crop_path,
        historical_vehicle_image=hist_vehicle_img,
        current_plate_image=current_obs.plate_crop_path,
        historical_plate_image=hist_plate_img,
        visual_similarity=sim_val,
        identity_event=current_obs.event_type.value,
        rule_used=alert_info.get("rule", "Analytical Rule"),
        requires_manual_review=alert_info.get("requires_manual_review", False),
        alert_title=alert_info.get("title", ""),
        alert_message=alert_info.get("message", ""),
        action_required=alert_info.get("action", ""),
        timestamp=current_obs.timestamp,
        historical_timestamp=hist_timestamp,
        camera_id=current_obs.camera_id,
        zone=current_obs.zone,
        plate_confidence=current_obs.plate_confidence,
        ocr_confidence=current_obs.ocr_confidence
    )

def reset_demo_data() -> Dict[str, int]:
    """
    Safely purges only records marked with is_demo = 1.
    Guarantees that production data, schema, and source files remain untouched.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM detections WHERE is_demo = 1")
    d_count = cursor.rowcount
    cursor.execute("DELETE FROM identity_observations WHERE is_demo = 1")
    o_count = cursor.rowcount
    cursor.execute("DELETE FROM vehicle_identities WHERE is_demo = 1")
    v_count = cursor.rowcount
    conn.commit()
    conn.close()
    return {
        "deleted_detections": d_count,
        "deleted_observations": o_count,
        "deleted_vehicles": v_count
    }
