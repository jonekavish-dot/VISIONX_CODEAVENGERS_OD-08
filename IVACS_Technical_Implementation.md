# IVACS Technical Implementation Guide

## Code Architecture & Quick Start

---

## 1. DETECTION PIPELINE

### YOLOv8 License Plate Detection

```python
# detection_engine.py
import cv2
import torch
from ultralytics import YOLO
import numpy as np

class PlateDetectionEngine:
    def __init__(self, model_path="yolov8m.pt"):
        self.model = YOLO(model_path)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)
        
    def detect_plates(self, frame):
        """
        Detect license plates in frame
        Returns: List of {bbox, confidence}
        """
        results = self.model(frame, conf=0.5, iou=0.45)
        
        detections = []
        for r in results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0])
                
                detections.append({
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'confidence': conf
                })
        
        return detections
    
    def extract_plate_region(self, frame, bbox):
        """Extract ROI containing license plate"""
        x1, y1, x2, y2 = bbox
        plate_roi = frame[y1:y2, x1:x2]
        return plate_roi
```

### OCR Character Recognition

```python
# ocr_service.py
import easyocr
from typing import Tuple

class OCRService:
    def __init__(self):
        self.reader = easyocr.Reader(['en'], gpu=True)
        # Plate format validation patterns
        self.plate_patterns = {
            'india': r'^[A-Z]{2}\d{2}[A-Z]{2}\d{4}$',
            'indian_commercial': r'^[A-Z]{2}\d{2}[A-Z]{1}\d{4}$'
        }
    
    def extract_text(self, plate_roi) -> Tuple[str, float]:
        """
        Extract plate number from ROI
        Returns: (plate_text, confidence)
        """
        results = self.reader.readtext(plate_roi, detail=1)
        
        plate_text = ""
        confidences = []
        
        for detection in results:
            text, conf = detection[1], detection[2]
            plate_text += text
            confidences.append(conf)
        
        avg_confidence = np.mean(confidences) if confidences else 0
        
        # Post-processing: clean up OCR errors
        plate_text = self._post_process(plate_text)
        
        return plate_text, avg_confidence
    
    def _post_process(self, text: str) -> str:
        """Clean up OCR artifacts"""
        # Common replacements: O->0, I->1, S->5
        replacements = {
            'O': '0', 'I': '1', 'S': '5', 'Z': '2',
            'l': '1', 'o': '0'
        }
        
        text = text.upper()
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text.strip()
```

---

## 2. VEHICLE CLASSIFICATION

### Multi-Attribute Vehicle Classifier

```python
# vehicle_classifier.py
import torch
import torchvision.models as models
from torchvision import transforms
import cv2

class VehicleClassifier:
    def __init__(self, model_path="resnet50_vehicle.pt"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = models.resnet50(pretrained=True)
        
        # Replace final layer for multi-task learning
        num_classes = {
            'color': 5,      # red, blue, white, black, silver
            'make': 50,      # vehicle brands
            'body_type': 6   # sedan, suv, truck, van, bus, other
        }
        
        in_features = self.model.fc.in_features
        self.model.fc = torch.nn.ModuleDict({
            'color': torch.nn.Linear(in_features, num_classes['color']),
            'make': torch.nn.Linear(in_features, num_classes['make']),
            'body_type': torch.nn.Linear(in_features, num_classes['body_type'])
        })
        
        checkpoint = torch.load(model_path, map_location=self.device)
        self.model.load_state_dict(checkpoint)
        self.model.to(self.device)
        self.model.eval()
        
        self.transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
    
    def classify(self, vehicle_roi):
        """
        Classify vehicle attributes
        Returns: {color, make, body_type, confidences}
        """
        # Prepare input
        tensor = self.transform(cv2.cvtColor(vehicle_roi, cv2.COLOR_BGR2RGB))
        tensor = tensor.unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            features = self.model.features(tensor)
            
            color_logits = self.model.fc['color'](features)
            make_logits = self.model.fc['make'](features)
            body_logits = self.model.fc['body_type'](features)
        
        # Get predictions
        color_pred = torch.argmax(color_logits, dim=1).item()
        make_pred = torch.argmax(make_logits, dim=1).item()
        body_pred = torch.argmax(body_logits, dim=1).item()
        
        color_conf = torch.softmax(color_logits, dim=1)[0, color_pred].item()
        make_conf = torch.softmax(make_logits, dim=1)[0, make_pred].item()
        body_conf = torch.softmax(body_logits, dim=1)[0, body_pred].item()
        
        return {
            'color': self.color_map[color_pred],
            'color_conf': color_conf,
            'make': self.make_map[make_pred],
            'make_conf': make_conf,
            'body_type': self.body_type_map[body_pred],
            'body_type_conf': body_conf
        }
    
    color_map = {0: 'red', 1: 'blue', 2: 'white', 3: 'black', 4: 'silver'}
    make_map = {0: 'Toyota', 1: 'Honda', 2: 'Maruti', 3: 'Hyundai', ...}
    body_type_map = {0: 'sedan', 1: 'suv', 2: 'truck', 3: 'van', 4: 'bus', 5: 'other'}
```

---

## 3. BEHAVIOR ANALYSIS

### Temporal Pattern Mining

```python
# behavior_analyzer.py
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from datetime import datetime, timedelta

class BehaviorAnalyzer:
    def __init__(self, anomaly_threshold=0.7):
        self.anomaly_model = IsolationForest(
            contamination=0.05,
            random_state=42
        )
        self.anomaly_threshold = anomaly_threshold
        self.vehicle_history = {}  # in-memory cache
    
    def calculate_dwell_time(self, entry_time, exit_time):
        """Calculate vehicle dwell time in minutes"""
        return (exit_time - entry_time).total_seconds() / 60
    
    def track_vehicle(self, plate_number, timestamp, vehicle_info):
        """Track vehicle visit"""
        if plate_number not in self.vehicle_history:
            self.vehicle_history[plate_number] = {
                'visits': [],
                'last_seen': None,
                'visit_count': 0
            }
        
        history = self.vehicle_history[plate_number]
        history['visits'].append({
            'timestamp': timestamp,
            'vehicle_info': vehicle_info
        })
        history['last_seen'] = timestamp
        history['visit_count'] += 1
        
        return history
    
    def calculate_anomaly_score(self, plate_number) -> float:
        """
        Calculate anomaly score for vehicle
        Returns: 0-1 (higher = more anomalous)
        """
        history = self.vehicle_history.get(plate_number, {})
        visits = history.get('visits', [])
        
        if len(visits) < 2:
            return 0.0  # Not enough data
        
        # Feature extraction
        features = []
        for i in range(1, len(visits)):
            time_between = (visits[i]['timestamp'] - visits[i-1]['timestamp']).total_seconds() / 3600
            visit_count = len(visits)
            hour_of_day = visits[i]['timestamp'].hour
            
            features.append([time_between, visit_count, hour_of_day])
        
        features = np.array(features)
        
        # Train on historical patterns
        if len(features) > 5:
            self.anomaly_model.fit(features)
            anomaly_score = -self.anomaly_model.score_samples(features[-1:])
            return float(np.clip(anomaly_score[0], 0, 1))
        
        return 0.0
    
    def detect_suspicious_patterns(self, plate_number) -> dict:
        """Detect multiple suspicious patterns"""
        history = self.vehicle_history.get(plate_number, {})
        visits = history.get('visits', [])
        
        alerts = []
        
        # Pattern 1: Frequent visits
        if len(visits) > 5:
            recent_visits = [v for v in visits if 
                           (datetime.now() - v['timestamp']).days <= 7]
            if len(recent_visits) > 3:
                alerts.append({
                    'type': 'HIGH_VISIT_FREQUENCY',
                    'severity': 'MEDIUM',
                    'detail': f'{len(recent_visits)} visits in 7 days'
                })
        
        # Pattern 2: Unusual hours
        if visits:
            last_visit_hour = visits[-1]['timestamp'].hour
            if last_visit_hour < 6 or last_visit_hour > 22:
                alerts.append({
                    'type': 'UNUSUAL_TIME',
                    'severity': 'LOW',
                    'detail': f'Visit at {last_visit_hour}:00'
                })
        
        # Pattern 3: Prolonged dwell time
        # (Calculated from video duration)
        
        return {
            'plate': plate_number,
            'anomaly_score': self.calculate_anomaly_score(plate_number),
            'alerts': alerts
        }
```

---

## 4. DATABASE SCHEMA

### PostgreSQL Schema

```sql
-- Vehicles table
CREATE TABLE vehicles (
    id SERIAL PRIMARY KEY,
    plate_number VARCHAR(20) UNIQUE NOT NULL,
    color VARCHAR(20),
    make VARCHAR(50),
    model VARCHAR(50),
    body_type VARCHAR(20),
    status VARCHAR(20) DEFAULT 'ACTIVE', -- ACTIVE, BLACKLISTED, PERMIT_EXPIRED
    first_seen TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP,
    visit_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_plate (plate_number),
    INDEX idx_status (status),
    INDEX idx_last_seen (last_seen)
);

-- Vehicle history table (partitioned by date)
CREATE TABLE vehicle_history (
    id BIGSERIAL PRIMARY KEY,
    vehicle_id INT REFERENCES vehicles(id),
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    entry_frame_id VARCHAR(100),
    exit_frame_id VARCHAR(100),
    dwell_time_minutes INT,
    zone_id INT,
    confidence FLOAT,
    detection_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    PARTITION BY RANGE (created_at)
);

-- Permits table
CREATE TABLE permits (
    id SERIAL PRIMARY KEY,
    plate_number VARCHAR(20) NOT NULL,
    site_id INT NOT NULL,
    permit_type VARCHAR(50), -- DAILY, WEEKLY, MONTHLY, PERMANENT
    issue_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    authorized_by VARCHAR(100),
    status VARCHAR(20) DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (plate_number) REFERENCES vehicles(plate_number),
    INDEX idx_plate_expiry (plate_number, expiry_date)
);

-- Blacklist table
CREATE TABLE blacklist (
    id SERIAL PRIMARY KEY,
    plate_number VARCHAR(20) NOT NULL,
    reason VARCHAR(255),
    added_by VARCHAR(100),
    added_date TIMESTAMP DEFAULT NOW(),
    expiry_date TIMESTAMP,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    FOREIGN KEY (plate_number) REFERENCES vehicles(plate_number),
    UNIQUE KEY uk_plate_status (plate_number, status)
);

-- Alerts table
CREATE TABLE alerts (
    id BIGSERIAL PRIMARY KEY,
    vehicle_id INT REFERENCES vehicles(id),
    alert_type VARCHAR(100), -- BLACKLIST_HIT, PERMIT_EXPIRED, ANOMALY, etc.
    severity VARCHAR(20), -- CRITICAL, HIGH, MEDIUM, LOW
    message TEXT,
    detection_frame_id VARCHAR(100),
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_created (created_at),
    INDEX idx_severity (severity),
    INDEX idx_acknowledged (acknowledged)
);

-- Anomaly scores
CREATE TABLE anomaly_scores (
    id BIGSERIAL PRIMARY KEY,
    vehicle_id INT REFERENCES vehicles(id),
    score FLOAT,
    features JSONB,
    detected_anomalies TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_vehicle_created (vehicle_id, created_at)
);
```

---

## 5. API LAYER

### FastAPI Server

```python
# main.py
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from datetime import datetime

app = FastAPI(title="IVACS API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
from detection_engine import PlateDetectionEngine
from ocr_service import OCRService
from vehicle_classifier import VehicleClassifier
from behavior_analyzer import BehaviorAnalyzer
from database import Database

detection_engine = PlateDetectionEngine()
ocr_service = OCRService()
vehicle_classifier = VehicleClassifier()
behavior_analyzer = BehaviorAnalyzer()
db = Database()

# WebSocket manager for real-time alerts
connected_clients = []

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception as e:
        connected_clients.remove(websocket)

async def broadcast_alert(alert):
    for client in connected_clients:
        try:
            await client.send_json(alert)
        except:
            pass

# REST Endpoints

@app.get("/vehicles/{plate}")
async def get_vehicle_history(plate: str):
    """Get complete vehicle history"""
    vehicle = db.get_vehicle(plate)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    history = db.get_vehicle_history(plate)
    blacklist_status = db.check_blacklist(plate)
    permit_status = db.check_permit(plate)
    
    return {
        'vehicle': vehicle,
        'history': history,
        'blacklist_status': blacklist_status,
        'permit_status': permit_status,
        'anomaly_score': behavior_analyzer.calculate_anomaly_score(plate)
    }

@app.post("/permits/verify")
async def verify_permit(plate: str, site_id: int):
    """Verify vehicle permit"""
    permit = db.check_permit(plate, site_id)
    
    if not permit:
        return {
            'valid': False,
            'reason': 'No permit found'
        }
    
    if datetime.now().date() > permit['expiry_date']:
        return {
            'valid': False,
            'reason': 'Permit expired'
        }
    
    return {
        'valid': True,
        'permit_type': permit['permit_type'],
        'expires_on': permit['expiry_date'].isoformat()
    }

@app.get("/alerts/active")
async def get_active_alerts(limit: int = 50):
    """Get unacknowledged alerts"""
    alerts = db.get_unacknowledged_alerts(limit)
    return {'alerts': alerts, 'count': len(alerts)}

@app.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int, user: str):
    """Acknowledge an alert"""
    db.acknowledge_alert(alert_id, user)
    return {'status': 'acknowledged'}

@app.get("/analytics/daily-report")
async def get_daily_report(date: str = None):
    """Get daily analytics report"""
    if not date:
        date = datetime.now().date()
    
    return {
        'date': date.isoformat(),
        'total_vehicles': db.count_vehicles_by_date(date),
        'alerts_triggered': db.count_alerts_by_date(date),
        'blacklist_hits': db.count_blacklist_hits(date),
        'permit_violations': db.count_permit_violations(date),
        'top_vehicles': db.get_top_vehicles(date, limit=10)
    }

# Detection webhook (called by video processor)
@app.post("/detections")
async def process_detection(detection: dict):
    """
    Process vehicle detection
    detection = {
        'frame_id': str,
        'timestamp': datetime,
        'plate': str,
        'confidence': float,
        'vehicle_info': {...}
    }
    """
    plate = detection['plate']
    timestamp = detection['timestamp']
    
    # Update vehicle record
    vehicle = db.get_or_create_vehicle(plate, detection['vehicle_info'])
    
    # Track behavior
    behavior_analyzer.track_vehicle(plate, timestamp, detection['vehicle_info'])
    
    # Check permit
    permit_valid = db.check_permit(plate)
    
    # Check blacklist
    is_blacklisted = db.check_blacklist(plate)
    
    # Calculate anomaly
    anomaly_score = behavior_analyzer.calculate_anomaly_score(plate)
    suspicious = behavior_analyzer.detect_suspicious_patterns(plate)
    
    # Generate alerts
    alerts = []
    
    if is_blacklisted:
        alert = {
            'type': 'BLACKLIST_HIT',
            'severity': 'CRITICAL',
            'vehicle_id': vehicle['id'],
            'message': f'Blacklisted vehicle detected: {plate}'
        }
        db.create_alert(alert)
        alerts.append(alert)
    
    if not permit_valid:
        alert = {
            'type': 'PERMIT_INVALID',
            'severity': 'HIGH',
            'vehicle_id': vehicle['id'],
            'message': f'Vehicle without valid permit: {plate}'
        }
        db.create_alert(alert)
        alerts.append(alert)
    
    if anomaly_score > 0.7:
        alert = {
            'type': 'ANOMALOUS_BEHAVIOR',
            'severity': 'MEDIUM',
            'vehicle_id': vehicle['id'],
            'message': f'Suspicious pattern detected for {plate}'
        }
        db.create_alert(alert)
        alerts.append(alert)
    
    # Broadcast alerts
    for alert in alerts:
        await broadcast_alert(alert)
    
    return {
        'status': 'processed',
        'alerts': alerts,
        'anomaly_score': anomaly_score
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 6. VIDEO PROCESSING LOOP

### Real-time Stream Processor

```python
# video_processor.py
import cv2
import threading
from queue import Queue
from detection_engine import PlateDetectionEngine
from ocr_service import OCRService
from vehicle_classifier import VehicleClassifier
import requests
from datetime import datetime

class VideoProcessor:
    def __init__(self, stream_url, api_endpoint="http://localhost:8000"):
        self.stream_url = stream_url
        self.api_endpoint = api_endpoint
        self.detection_engine = PlateDetectionEngine()
        self.ocr_service = OCRService()
        self.vehicle_classifier = VehicleClassifier()
        self.frame_queue = Queue(maxsize=30)
        self.running = False
    
    def start(self):
        """Start processing stream"""
        self.running = True
        
        # Start capture thread
        capture_thread = threading.Thread(target=self._capture_frames)
        capture_thread.daemon = True
        capture_thread.start()
        
        # Start processing thread
        process_thread = threading.Thread(target=self._process_frames)
        process_thread.daemon = True
        process_thread.start()
    
    def _capture_frames(self):
        """Capture frames from RTSP/HTTP stream"""
        cap = cv2.VideoCapture(self.stream_url)
        frame_count = 0
        
        while self.running:
            ret, frame = cap.read()
            if not ret:
                continue
            
            frame_count += 1
            if frame_count % 3 == 0:  # Process every 3rd frame (10 FPS)
                try:
                    self.frame_queue.put_nowait((frame, datetime.now()))
                except:
                    pass  # Queue full, skip frame
        
        cap.release()
    
    def _process_frames(self):
        """Process frames for detection"""
        while self.running:
            try:
                frame, timestamp = self.frame_queue.get(timeout=1)
            except:
                continue
            
            # Detect plates
            detections = self.detection_engine.detect_plates(frame)
            
            for detection in detections:
                try:
                    # Extract plate ROI
                    plate_roi = self.detection_engine.extract_plate_region(
                        frame, detection['bbox']
                    )
                    
                    # OCR
                    plate_text, ocr_conf = self.ocr_service.extract_text(plate_roi)
                    
                    # Skip low confidence
                    if ocr_conf < 0.6:
                        continue
                    
                    # Get vehicle region (expand bbox for vehicle classification)
                    x1, y1, x2, y2 = detection['bbox']
                    vehicle_roi = frame[
                        max(0, y1-100):min(frame.shape[0], y2+100),
                        max(0, x1-100):min(frame.shape[1], x2+100)
                    ]
                    
                    # Classify vehicle
                    vehicle_info = self.vehicle_classifier.classify(vehicle_roi)
                    
                    # Send to API
                    detection_data = {
                        'frame_id': f"{timestamp.isoformat()}_{hash(plate_text)}",
                        'timestamp': timestamp.isoformat(),
                        'plate': plate_text,
                        'confidence': float(detection['confidence']),
                        'vehicle_info': vehicle_info
                    }
                    
                    response = requests.post(
                        f"{self.api_endpoint}/detections",
                        json=detection_data,
                        timeout=2
                    )
                    
                    print(f"✓ Detected: {plate_text} (Conf: {ocr_conf:.2f})")
                
                except Exception as e:
                    print(f"✗ Error processing detection: {e}")

# Usage
if __name__ == "__main__":
    processor = VideoProcessor("rtsp://camera1.local/stream")
    processor.start()
    
    # Keep running
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        processor.running = False
```

---

## 7. DEPLOYMENT

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: ivacs
      POSTGRES_USER: ivacs_user
      POSTGRES_PASSWORD: secure_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  api:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://ivacs_user:secure_password@postgres:5432/ivacs
      REDIS_URL: redis://redis:6379
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app
    command: uvicorn main:app --host 0.0.0.0 --reload

  video-processor:
    build: ./processor
    environment:
      API_ENDPOINT: http://api:8000
      RTSP_URL: rtsp://camera1.local/stream
    depends_on:
      - api
    volumes:
      - ./processor:/app

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      REACT_APP_API_URL: http://localhost:8000
    depends_on:
      - api

volumes:
  postgres_data:
  redis_data:
```

### Kubernetes Deployment

```yaml
# k8s/api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ivacs-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ivacs-api
  template:
    metadata:
      labels:
        app: ivacs-api
    spec:
      containers:
      - name: api
        image: ivacs-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: ivacs-secrets
              key: database-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
```

---

## PERFORMANCE OPTIMIZATION TIPS

1. **Model Inference:**
   - Use ONNX format for 2x speedup
   - Batch process frames for better GPU utilization
   - Quantize models (FP16) for lower memory

2. **Database:**
   - Use connection pooling (PgBouncer)
   - Partition vehicle_history by date
   - Create indexes on hot columns
   - Use Read Replicas for analytics queries

3. **Caching:**
   - Cache permits in Redis with 1-hour TTL
   - Cache blacklist with 30-minute TTL
   - Use query result caching

4. **API:**
   - Implement request batching
   - Use gzip compression
   - Cache responses (Redis)
   - Rate limiting

---

## MONITORING & LOGGING

```python
# monitoring.py
import logging
from prometheus_client import Counter, Histogram, start_http_server
import time

# Prometheus metrics
detections_total = Counter('detections_total', 'Total detections')
ocr_accuracy = Histogram('ocr_accuracy', 'OCR accuracy')
processing_time = Histogram('processing_time', 'Frame processing time')
api_requests = Counter('api_requests_total', 'Total API requests')

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Start Prometheus endpoint
start_http_server(8001)

def log_detection(plate, confidence):
    logger.info(f"Detection: {plate} ({confidence:.2f})")
    detections_total.inc()

def log_processing_time(duration):
    processing_time.observe(duration)
    if duration > 0.5:
        logger.warning(f"Slow processing: {duration:.2f}s")
```

---

## NEXT STEPS

1. **Clone repository structure**
2. **Setup dev environment** with Docker
3. **Start with Week 1-2 tasks**
4. **Run weekly sprints** with demo to stakeholders
5. **Iterate on MVP** based on feedback

This implementation guide provides the core architecture. Customize based on your specific requirements and infrastructure.
