"""
IVACS V-TRACE Vehicle Detector
Ultralytics YOLO-based detector targeting car, truck, bus, motorcycle.
Designed for high-responsiveness demo inference on developer laptops.
"""

import logging
from typing import List, Dict, Any, Optional
import numpy as np
import torch
from datetime import datetime
from ultralytics import YOLO
from backend.config import VEHICLE_CONF_THRESHOLD, TARGET_VEHICLE_CLASSES

logger = logging.getLogger("vtrace.vehicle_detector")

class VehicleDetector:
    """Detects vehicles in video frames using YOLOv8 nano/small."""
    
    # Standard COCO vehicle class mappings
    VEHICLE_CLASS_MAP = {
        2: "car",
        3: "motorcycle",
        5: "bus",
        7: "truck"
    }

    def __init__(self, model_name: str = "yolov8n.pt", conf_thresh: float = VEHICLE_CONF_THRESHOLD):
        self.conf_thresh = conf_thresh
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing VehicleDetector with {model_name} on device: {self.device}")
        try:
            self.model = YOLO(model_name)
        except Exception as e:
            logger.error(f"Failed to load YOLO model {model_name}: {e}")
            raise e

    def detect(self, frame: np.ndarray, frame_number: int = 0) -> List[Dict[str, Any]]:
        """
        Detects vehicles in the given frame.
        
        Returns:
            List of dicts:
            [{
                'vehicle_class': str,
                'vehicle_confidence': float,
                'vehicle_bbox': [x1, y1, x2, y2],
                'frame_number': int,
                'timestamp': str
            }, ...]
        """
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return []

        timestamp_str = datetime.now().isoformat()
        detections = []

        try:
            # Run inference targeting vehicle classes only
            target_class_ids = list(self.VEHICLE_CLASS_MAP.keys())
            results = self.model(
                frame,
                classes=target_class_ids,
                conf=self.conf_thresh,
                iou=0.45,
                max_det=30,
                verbose=False,
                device=self.device
            )

            if not results or len(results) == 0:
                return []

            boxes = results[0].boxes
            if boxes is None or len(boxes) == 0:
                return []

            h, w = frame.shape[:2]

            for box in boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                xyxy = box.xyxy[0].cpu().numpy()
                
                x1 = max(0, int(xyxy[0]))
                y1 = max(0, int(xyxy[1]))
                x2 = min(w, int(xyxy[2]))
                y2 = min(h, int(xyxy[3]))

                # Validate valid bbox dimensions
                if x2 <= x1 or y2 <= y1:
                    continue

                v_class = self.VEHICLE_CLASS_MAP.get(cls_id, "vehicle")
                detections.append({
                    "vehicle_class": v_class,
                    "vehicle_confidence": round(conf, 3),
                    "vehicle_bbox": [x1, y1, x2, y2],
                    "frame_number": frame_number,
                    "timestamp": timestamp_str
                })

            # Spatial sort left-to-right for multi-vehicle lane consistency
            detections.sort(key=lambda d: d["vehicle_bbox"][0])
            for idx, det in enumerate(detections, start=1):
                det["vehicle_index"] = idx

        except Exception as e:
            logger.error(f"Error during vehicle detection on frame {frame_number}: {e}")
            return []

        return detections
