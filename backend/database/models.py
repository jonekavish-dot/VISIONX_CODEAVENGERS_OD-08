"""
IVACS V-TRACE Database Models Definition
Defines the SQLite schema representation and constants for the detections table.
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

TABLE_COLUMNS = [
    "id", "camera_id", "zone", "timestamp", "frame_number", "status",
    "vehicle_class", "vehicle_confidence", "plate", "raw_plate",
    "plate_confidence", "ocr_confidence", "vehicle_bbox", "plate_bbox",
    "vehicle_crop_path", "plate_crop_path", "frame_path", "annotated_frame_path", "created_at"
]
