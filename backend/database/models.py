"""
IVACS V-TRACE Database Models Definition
Defines the SQLite schema representations for detections, vehicle identities,
identity observations, vehicle registry, site permits, camera zones, route rules,
vehicle transit history, and security alerts.
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
    vehicle_id TEXT,
    visual_similarity REAL,
    identity_event TEXT,
    identity_match_status TEXT,
    is_demo INTEGER DEFAULT 0,
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
    is_demo INTEGER DEFAULT 0,
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
    previous_crop_path TEXT,
    is_demo INTEGER DEFAULT 0
);
"""

VEHICLE_REGISTRY_SCHEMA = """
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
);
"""

PERMITS_SCHEMA = """
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
);
"""

CAMERA_ZONES_SCHEMA = """
CREATE TABLE IF NOT EXISTS camera_zones (
    camera_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    zone TEXT NOT NULL,
    description TEXT NOT NULL
);
"""

ROUTE_RULES_SCHEMA = """
CREATE TABLE IF NOT EXISTS route_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_zone TEXT NOT NULL,
    to_zone TEXT NOT NULL,
    minimum_travel_seconds INTEGER NOT NULL,
    maximum_travel_seconds INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);
"""

VEHICLE_TRANSIT_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS vehicle_transit_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id TEXT NOT NULL,
    plate TEXT,
    camera_id TEXT NOT NULL,
    zone TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    is_demo INTEGER DEFAULT 1
);
"""

ALERTS_SCHEMA = """
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
);
"""
