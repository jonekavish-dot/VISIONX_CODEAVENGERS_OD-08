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

    # 4. Vehicle Registry Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicle_registry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plate TEXT UNIQUE NOT NULL,
        registration_date TEXT,
        manufacturer TEXT,
        model TEXT,
        colour TEXT,
        vehicle_type TEXT,
        fuel_type TEXT,
        insurance_status TEXT,
        fitness_status TEXT,
        pucc_status TEXT,
        source TEXT NOT NULL DEFAULT 'DEMO_REGISTRY',
        is_demo INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    # 5. Permits Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS permits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plate TEXT NOT NULL,
        site_id TEXT NOT NULL DEFAULT 'SITE-BLR-01',
        allowed_zones TEXT NOT NULL,
        valid_from TEXT NOT NULL,
        valid_until TEXT NOT NULL,
        purpose TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        is_demo INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """)

    # 6. Camera Zones Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS camera_zones (
        camera_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        zone TEXT NOT NULL,
        description TEXT NOT NULL
    )
    """)

    # 7. Route Rules Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS route_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_zone TEXT NOT NULL,
        to_zone TEXT NOT NULL,
        minimum_travel_seconds INTEGER NOT NULL,
        maximum_travel_seconds INTEGER NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1
    )
    """)

    # 8. Vehicle Transit History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicle_transit_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id TEXT NOT NULL,
        plate TEXT,
        camera_id TEXT NOT NULL,
        zone TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        is_demo INTEGER DEFAULT 1
    )
    """)

    # 9. Alerts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        vehicle_id TEXT,
        plate TEXT,
        camera_id TEXT NOT NULL,
        zone TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        title TEXT NOT NULL,
        reason TEXT NOT NULL,
        action_required TEXT NOT NULL,
        requires_manual_review INTEGER NOT NULL DEFAULT 1,
        evidence_json TEXT NOT NULL DEFAULT '{}',
        review_status TEXT NOT NULL DEFAULT 'PENDING',
        is_demo INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

    # Seed demo configurations if empty
    seed_all_demo_data()


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
    cursor.execute("DELETE FROM alerts WHERE is_demo = 1")
    a_count = cursor.rowcount
    cursor.execute("DELETE FROM vehicle_transit_history WHERE is_demo = 1")
    t_count = cursor.rowcount
    conn.commit()
    conn.close()
    return {
        "deleted_detections": d_count,
        "deleted_observations": o_count,
        "deleted_vehicles": v_count,
        "deleted_alerts": a_count,
        "deleted_transits": t_count
    }


# ==================== SEEDING OPERATIONS ====================

def seed_all_demo_data():
    """Seeds demo registry, permits, camera zones, and route rules if tables are empty."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Seed Camera Zones
    cursor.execute("SELECT COUNT(*) FROM camera_zones")
    if cursor.fetchone()[0] == 0:
        zones = [
            ("CAM-01", "Gate Entrance", "GATE_IN", "Primary site entry gate equipped with vehicle inspection and ANPR."),
            ("CAM-02", "Material Yard", "MATERIAL_YARD", "Heavy materials staging, unloading, and supply depot."),
            ("CAM-03", "Active Zone", "ACTIVE_ZONE", "Core building superstructure and active equipment zone."),
            ("CAM-04", "Gate Exit", "GATE_OUT", "Departure gate with outbound vehicle compliance verification.")
        ]
        cursor.executemany("INSERT INTO camera_zones (camera_id, name, zone, description) VALUES (?, ?, ?, ?)", zones)

    # 2. Seed Route Rules
    cursor.execute("SELECT COUNT(*) FROM route_rules")
    if cursor.fetchone()[0] == 0:
        rules = [
            ("GATE_IN", "MATERIAL_YARD", 10, 600, 1),
            ("MATERIAL_YARD", "ACTIVE_ZONE", 15, 1200, 1),
            ("ACTIVE_ZONE", "GATE_OUT", 15, 1200, 1),
            ("GATE_IN", "ACTIVE_ZONE", 20, 1200, 1),
            ("MATERIAL_YARD", "GATE_OUT", 30, 1800, 1)
        ]
        cursor.executemany("""
            INSERT INTO route_rules (from_zone, to_zone, minimum_travel_seconds, maximum_travel_seconds, enabled)
            VALUES (?, ?, ?, ?, ?)
        """, rules)

    # 3. Seed Demo Vehicle Registry
    cursor.execute("SELECT COUNT(*) FROM vehicle_registry")
    if cursor.fetchone()[0] == 0:
        now_iso = datetime.now().isoformat()
        registry_vehicles = [
            ("TN01AB1234", "2021-04-12", "Tata", "Starbus", "WHITE", "bus", "DIESEL", "VALID", "VALID", "VALID", "DEMO_REGISTRY", 1, now_iso, now_iso),
            ("MH12DE1433", "2020-08-19", "Hyundai", "Verna", "WHITE", "car", "DIESEL", "VALID", "VALID", "VALID", "DEMO_REGISTRY", 1, now_iso, now_iso),
            ("KA01AB1234", "2019-11-03", "Tata", "Tiago", "BLUE", "car", "PETROL", "EXPIRED", "VALID", "VALID", "DEMO_REGISTRY", 1, now_iso, now_iso),
            ("DL01XY9999", "2022-01-15", "Ashok Leyland", "Captain 2518", "YELLOW", "truck", "DIESEL", "VALID", "VALID", "VALID", "DEMO_REGISTRY", 1, now_iso, now_iso),
            ("HR26DQ5555", "2018-05-20", "Tata", "Marcopolo", "ORANGE", "bus", "DIESEL", "VALID", "EXPIRED", "EXPIRED", "DEMO_REGISTRY", 1, now_iso, now_iso)
        ]
        cursor.executemany("""
            INSERT INTO vehicle_registry (
                plate, registration_date, manufacturer, model, colour,
                vehicle_type, fuel_type, insurance_status, fitness_status,
                pucc_status, source, is_demo, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, registry_vehicles)

    # 4. Seed Demo Permits
    cursor.execute("SELECT COUNT(*) FROM permits")
    if cursor.fetchone()[0] == 0:
        now_iso = datetime.now().isoformat()
        permits_data = [
            ("TN01AB1234", "SITE-BLR-01", json.dumps(["GATE_IN", "MATERIAL_YARD", "ACTIVE_ZONE", "GATE_OUT"]), "2024-01-01", "2027-12-31", "Material Delivery & Site Operations", "ACTIVE", 1, now_iso),
            ("MH12DE1433", "SITE-BLR-01", json.dumps(["GATE_IN", "MATERIAL_YARD", "ACTIVE_ZONE", "GATE_OUT"]), "2024-01-01", "2027-12-31", "Supervisory Inspection Vehicle", "ACTIVE", 1, now_iso),
            ("KA01AB1234", "SITE-BLR-01", json.dumps(["GATE_IN", "MATERIAL_YARD", "ACTIVE_ZONE", "GATE_OUT"]), "2024-01-01", "2025-01-01", "Subcontractor Supply (Expired)", "EXPIRED", 1, now_iso),
            ("DL01XY9999", "SITE-BLR-01", json.dumps(["GATE_IN", "MATERIAL_YARD"]), "2024-01-01", "2027-12-31", "Bulk Aggregate Hauler (Restricted Zone)", "ACTIVE", 1, now_iso)
        ]
        cursor.executemany("""
            INSERT INTO permits (
                plate, site_id, allowed_zones, valid_from, valid_until,
                purpose, status, is_demo, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, permits_data)

    conn.commit()
    conn.close()


# ==================== VEHICLE REGISTRY OPERATIONS ====================

def get_registry_record_by_plate(plate: str) -> Optional[Dict[str, Any]]:
    """Retrieves vehicle record from demo vehicle registry by plate."""
    if not plate:
        return None
    clean = plate.strip().upper().replace(" ", "").replace("-", "")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicle_registry WHERE REPLACE(REPLACE(plate, ' ', ''), '-', '') = ? LIMIT 1", (clean,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def reset_demo_registry_data() -> int:
    """Clears and re-seeds demo registry."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vehicle_registry WHERE is_demo = 1")
    count = cursor.rowcount
    conn.commit()
    conn.close()
    seed_all_demo_data()
    return count


# ==================== PERMITS OPERATIONS ====================

def get_permits_for_plate(plate: str) -> List[Dict[str, Any]]:
    """Fetches all site permits associated with a license plate."""
    if not plate:
        return []
    clean = plate.strip().upper().replace(" ", "").replace("-", "")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM permits WHERE REPLACE(REPLACE(plate, ' ', ''), '-', '') = ? ORDER BY id DESC", (clean,))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["allowed_zones"] = json.loads(d.get("allowed_zones", "[]"))
        except Exception:
            d["allowed_zones"] = []
        results.append(d)
    return results

def get_all_permits(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM permits ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["allowed_zones"] = json.loads(d.get("allowed_zones", "[]"))
        except Exception:
            d["allowed_zones"] = []
        results.append(d)
    return results


# ==================== CAMERA ZONES & ROUTE RULES ====================

def get_camera_zones() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM camera_zones ORDER BY camera_id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_route_rules() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM route_rules WHERE enabled = 1")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== VEHICLE TRANSIT HISTORY ====================

def record_vehicle_transit(
    vehicle_id: str,
    plate: Optional[str],
    camera_id: str,
    zone: str,
    timestamp: str,
    is_demo: bool = True
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO vehicle_transit_history (vehicle_id, plate, camera_id, zone, timestamp, is_demo)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (vehicle_id, plate, camera_id, zone, timestamp, 1 if is_demo else 0))
    transit_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return transit_id

def get_recent_transit_for_vehicle(vehicle_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM vehicle_transit_history 
        WHERE vehicle_id = ? 
        ORDER BY id DESC 
        LIMIT ?
    """, (vehicle_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== ALERTS OPERATIONS ====================

def insert_alert(
    alert_type: str,
    severity: str,
    vehicle_id: Optional[str],
    plate: Optional[str],
    camera_id: str,
    zone: str,
    timestamp: str,
    title: str,
    reason: str,
    action_required: str,
    requires_manual_review: bool = True,
    evidence_references: Optional[Dict[str, Any]] = None,
    is_demo: bool = False
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    ev_json = json.dumps(evidence_references or {})
    cursor.execute("""
        INSERT INTO alerts (
            alert_type, severity, vehicle_id, plate, camera_id, zone,
            timestamp, title, reason, action_required, requires_manual_review,
            evidence_json, review_status, is_demo, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
    """, (
        alert_type, severity, vehicle_id, plate, camera_id, zone,
        timestamp, title, reason, action_required,
        1 if requires_manual_review else 0,
        ev_json, 1 if is_demo else 0, datetime.now().isoformat()
    ))
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return alert_id

def get_alerts(
    limit: int = 50,
    offset: int = 0,
    plate: Optional[str] = None,
    camera_id: Optional[str] = None,
    zone: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None
) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM alerts WHERE 1=1"
    params = []
    if plate:
        query += " AND plate LIKE ?"
        params.append(f"%{plate.strip().upper()}%")
    if camera_id:
        query += " AND camera_id = ?"
        params.append(camera_id)
    if zone:
        query += " AND zone = ?"
        params.append(zone)
    if alert_type:
        query += " AND alert_type = ?"
        params.append(alert_type)
    if severity:
        query += " AND severity = ?"
        params.append(severity)
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["evidence_references"] = json.loads(d.get("evidence_json", "{}"))
        except Exception:
            d["evidence_references"] = {}
        d["requires_manual_review"] = bool(d.get("requires_manual_review", 1))
        results.append(d)
    return results

def get_alert_by_id(alert_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        try:
            d["evidence_references"] = json.loads(d.get("evidence_json", "{}"))
        except Exception:
            d["evidence_references"] = {}
        d["requires_manual_review"] = bool(d.get("requires_manual_review", 1))
        return d
    return None

def get_dashboard_summary_counts() -> Dict[str, int]:
    """Computes real-time telemetry metrics for command center KPI cards."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM vehicle_identities")
    active_vehicles = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM detections")
    detections = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM identity_observations 
        WHERE event_type IN ('POSSIBLE_IDENTITY_MISMATCH', 'POSSIBLE_PLATE_SWAP')
    """)
    identity_warnings = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM alerts 
        WHERE alert_type IN ('PERMIT_EXPIRED', 'UNAUTHORIZED_ZONE', 'NO_SITE_PERMIT', 'UNKNOWN_VEHICLE')
    """)
    access_alerts = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM alerts WHERE alert_type = 'ROUTE_INTEGRITY_ANOMALY'")
    route_alerts = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM detections WHERE status = 'PLATE_UNREADABLE'")
    unreadable_plates = cursor.fetchone()[0]

    conn.close()
    return {
        "active_vehicles": active_vehicles,
        "detections": detections,
        "identity_warnings": identity_warnings,
        "access_alerts": access_alerts,
        "route_alerts": route_alerts,
        "unreadable_plates": unreadable_plates
    }

def get_latest_observations_by_camera() -> Dict[str, Any]:
    """Returns the most recent vehicle detection event for each configured camera."""
    from backend.config import CAMERAS
    conn = get_connection()
    cursor = conn.cursor()
    results = {}
    for cam_id, cfg in CAMERAS.items():
        cursor.execute("""
            SELECT * FROM detections 
            WHERE camera_id = ? 
            ORDER BY id DESC 
            LIMIT 1
        """, (cam_id,))
        row = cursor.fetchone()
        if row:
            d = dict(row)
            results[cam_id] = {
                "camera_id": cam_id,
                "camera_name": cfg.name,
                "zone": cfg.zone,
                "plate": d.get("plate") or d.get("raw_plate") or "NO_PLATE",
                "vehicle_class": d.get("vehicle_class"),
                "status": d.get("status"),
                "frame_path": d.get("frame_path"),
                "vehicle_crop_path": d.get("vehicle_crop_path"),
                "plate_crop_path": d.get("plate_crop_path"),
                "annotated_frame_path": d.get("annotated_frame_path"),
                "timestamp": d.get("timestamp"),
                "identity_event": d.get("identity_event")
            }
        else:
            results[cam_id] = {
                "camera_id": cam_id,
                "camera_name": cfg.name,
                "zone": cfg.zone,
                "plate": "IDLE",
                "vehicle_class": None,
                "status": "IDLE",
                "frame_path": None,
                "vehicle_crop_path": None,
                "plate_crop_path": None,
                "annotated_frame_path": None,
                "timestamp": None,
                "identity_event": None
            }
    conn.close()
    return results

