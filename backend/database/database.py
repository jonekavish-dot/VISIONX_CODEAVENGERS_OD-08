"""
IVACS V-TRACE Database Access Layer
Uses standard SQLite3 for zero-overhead, reliable, hackathon-ready persistence.
"""

import sqlite3
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from backend.config import DB_PATH
from backend.schemas.detection import DetectionEvent, ProcessingStatus

def get_connection():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
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
        created_at TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

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
        vehicle_crop_path, plate_crop_path, frame_path, annotated_frame_path, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
