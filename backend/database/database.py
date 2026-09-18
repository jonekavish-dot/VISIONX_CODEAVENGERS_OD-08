"""
IVACS V-TRACE Database Access Layer
Uses standard SQLite3 for zero-overhead, reliable, hackathon-ready persistence.
Handles detections, persistent vehicle identities, and identity observations.
"""

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
        ("identity_match_status", "TEXT")
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
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

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
        previous_crop_path TEXT
    )
    """)

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
    cursor.execute("SELECT COUNT(*) FROM vehicle_identities")
    count = cursor.fetchone()[0]
    conn.close()
    return f"V-{count + 1:03d}"

def insert_vehicle_identity(identity: VehicleIdentity) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    emb_json = json.dumps(identity.embedding) if identity.embedding else "[]"
    cursor.execute("""
    INSERT INTO vehicle_identities (
        vehicle_id, canonical_plate, first_seen, last_seen, visit_count,
        vehicle_class, color, embedding_json, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        identity.vehicle_id,
        identity.canonical_plate,
        identity.first_seen,
        identity.last_seen,
        identity.visit_count,
        identity.vehicle_class,
        identity.color,
        emb_json,
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
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )

def get_vehicle_identity_by_id(vehicle_id: str) -> Optional[VehicleIdentity]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicle_identities WHERE vehicle_id = ?", (vehicle_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row_to_vehicle_identity(row)
    return None

def get_vehicle_identity_by_plate(plate: str) -> Optional[VehicleIdentity]:
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

def get_all_vehicle_identities() -> List[VehicleIdentity]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicle_identities ORDER BY last_seen DESC")
    rows = cursor.fetchall()
    conn.close()
    return [row_to_vehicle_identity(r) for r in rows]

# ==================== IDENTITY OBSERVATIONS OPERATIONS ====================

def insert_identity_observation(obs: "IdentityObservation") -> int:
    from backend.vehicle_identity.schemas import IdentityEventType
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO identity_observations (
        vehicle_identity_id, observed_plate, plate_confidence, ocr_confidence,
        visual_similarity, event_type, camera_id, zone, timestamp,
        frame_number, vehicle_crop_path, plate_crop_path, frame_path, previous_crop_path
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        obs.previous_crop_path
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
        previous_crop_path=row["previous_crop_path"]
    )

def get_identity_observations_for_vehicle(vehicle_id: str) -> List[IdentityObservation]:
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

def get_all_identity_observations(limit: int = 50, offset: int = 0) -> List[IdentityObservation]:
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

def get_latest_identity_observation() -> Optional[IdentityObservation]:
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
