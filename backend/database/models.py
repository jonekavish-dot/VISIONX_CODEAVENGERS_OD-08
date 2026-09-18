"""
IVACS V-TRACE Database Models Definition
Defines the SQLite schema representation and constants for detections,
vehicle_identities, and identity_observations.
"""

DETECTIONS_TABLE_SCHEMA = """
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
);
"""

VEHICLE_IDENTITIES_SCHEMA = """
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
);
"""

IDENTITY_OBSERVATIONS_SCHEMA = """
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
);
"""
