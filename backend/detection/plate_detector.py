"""
IVACS V-TRACE License Plate Detector
Modular plate detection module with vehicle-to-plate association.
Supports dedicated YOLO plate models and robust geometric/morphological ROI localization.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import cv2
import torch
from backend.config import PLATE_CONF_THRESHOLD

logger = logging.getLogger("vtrace.plate_detector")

class PlateDetector:
    """
    Detects license plates and associates each plate with its enclosing vehicle.
    Easily pluggable with custom-trained YOLO plate weights.
    """

    def __init__(self, model_path: Optional[str] = None, conf_thresh: float = PLATE_CONF_THRESHOLD):
        self.conf_thresh = conf_thresh
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Check if custom plate model weights exist
        if model_path and os.path.exists(model_path):
            try:
                from ultralytics import YOLO
                self.model = YOLO(model_path)
                logger.info(f"Loaded dedicated YOLO license plate model from {model_path}")
            except Exception as e:
                logger.warning(f"Could not load custom plate model {model_path}: {e}")

    def detect_in_vehicle(self, frame: np.ndarray, vehicle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Detects license plate inside a specific vehicle bounding box.
        
        Returns:
            Dict containing:
            {
                'plate_bbox': [x1, y1, x2, y2] (global coords),
                'plate_detection_confidence': float,
                'vehicle_association': vehicle,
                'plate_crop': np.ndarray
            } or None
        """
        if frame is None or vehicle is None:
            return None

        vx1, vy1, vx2, vy2 = vehicle["vehicle_bbox"]
        h_frame, w_frame = frame.shape[:2]
        
        # Clip to valid bounds
        vx1, vy1 = max(0, vx1), max(0, vy1)
        vx2, vy2 = min(w_frame, vx2), min(h_frame, vy2)
        
        v_width = vx2 - vx1
        v_height = vy2 - vy1
        if v_width < 20 or v_height < 20:
            return None

        vehicle_crop = frame[vy1:vy2, vx1:vx2]

        # Mode 1: Dedicated YOLO Plate Model if available
        if self.model is not None:
            try:
                results = self.model(vehicle_crop, conf=self.conf_thresh, verbose=False, device=self.device)
                if results and len(results) > 0 and results[0].boxes:
                    box = results[0].boxes[0]
                    conf = float(box.conf[0].item())
                    px1, py1, px2, py2 = box.xyxy[0].cpu().numpy().astype(int)
                    # Convert to global coordinates
                    gx1 = max(0, vx1 + px1)
                    gy1 = max(0, vy1 + py1)
                    gx2 = min(w_frame, vx1 + px2)
                    gy2 = min(h_frame, vy1 + py2)
                    
                    plate_crop = frame[gy1:gy2, gx1:gx2]
                    return {
                        "plate_bbox": [gx1, gy1, gx2, gy2],
                        "plate_detection_confidence": round(conf, 3),
                        "vehicle_association": vehicle,
                        "plate_crop": plate_crop
                    }
            except Exception as e:
                logger.debug(f"YOLO plate detection failed on vehicle crop: {e}")

        # Mode 2: High-contrast ROI localization for vehicle front/rear bumper region
        candidate = self._locate_plate_candidate(vehicle_crop, vx1, vy1, w_frame, h_frame)
        if candidate is not None:
            gx1, gy1, gx2, gy2, conf = candidate
            plate_crop = frame[gy1:gy2, gx1:gx2]
            if plate_crop.size > 0:
                return {
                    "plate_bbox": [gx1, gy1, gx2, gy2],
                    "plate_detection_confidence": round(conf, 3),
                    "vehicle_association": vehicle,
                    "plate_crop": plate_crop
                }

        return None

    def _locate_plate_candidate(
        self,
        vehicle_crop: np.ndarray,
        vx1: int,
        vy1: int,
        w_frame: int,
        h_frame: int
    ) -> Optional[Tuple[int, int, int, int, float]]:
        """
        Locates license plate candidate within vehicle crop using morphological gradient & contour analysis.
        License plates are characteristically high-contrast rectangles with aspect ratio between 2.0 and 5.5.
        """
        vh, vw = vehicle_crop.shape[:2]
        # Search specifically in lower bumper region (55% to 95% of the vehicle where plates reside)
        y_start = int(vh * 0.55)
        y_end = int(vh * 0.95)
        search_roi = vehicle_crop[y_start:y_end, :]
        if search_roi.size == 0:
            return None

        gray = cv2.cvtColor(search_roi, cv2.COLOR_BGR2GRAY)
        
        # Morphological gradient to highlight high contrast character/border edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (13, 5))
        morph = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)
        _, thresh = cv2.threshold(morph, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        best_candidate = None
        best_score = -1.0

        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w < 40 or h < 12:
                continue
            aspect = float(w) / float(h)
            area = w * h
            roi_area = vw * (y_end - y_start)
            rel_area = area / float(roi_area)

            # Indian & standard plates typically have aspect ratio 2.0 to 5.5
            if 2.0 <= aspect <= 5.5 and 0.01 <= rel_area <= 0.40:
                # Center-horizontal preference score
                center_dist = abs((x + w / 2.0) - (vw / 2.0)) / (vw / 2.0)
                score = (1.0 - center_dist * 0.6) * (1.0 - abs(aspect - 3.8) / 3.8)
                if score > best_score:
                    best_score = score
                    # Convert to vehicle coordinates
                    bx1 = max(0, x - 4)
                    by1 = max(0, (y + y_start) - 4)
                    bx2 = min(vw, x + w + 4)
                    by2 = min(vh, (y + y_start) + h + 4)
                    best_candidate = (bx1, by1, bx2, by2, min(0.95, max(0.50, 0.70 + score * 0.25)))

        if best_candidate is not None:
            bx1, by1, bx2, by2, conf = best_candidate
            gx1 = max(0, min(w_frame, vx1 + bx1))
            gy1 = max(0, min(h_frame, vy1 + by1))
            gx2 = max(0, min(w_frame, vx1 + bx2))
            gy2 = max(0, min(h_frame, vy1 + by2))
            if gx2 > gx1 and gy2 > gy1:
                return (gx1, gy1, gx2, gy2, conf)

        # Geometric fallback: default lower-middle bumper plate region
        # 15% to 85% width, 65% to 85% height of the vehicle
        fb_x1 = int(vx1 + vw * 0.25)
        fb_y1 = int(vy1 + vh * 0.65)
        fb_x2 = int(vx1 + vw * 0.75)
        fb_y2 = int(vy1 + vh * 0.85)
        
        gx1 = max(0, min(w_frame, fb_x1))
        gy1 = max(0, min(h_frame, fb_y1))
        gx2 = max(0, min(w_frame, fb_x2))
        gy2 = max(0, min(h_frame, fb_y2))
        
        if (gx2 - gx1) > 20 and (gy2 - gy1) > 10:
            return (gx1, gy1, gx2, gy2, 0.60)

        return None

    def detect_plates(self, frame: np.ndarray, vehicles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detects license plates across all detected vehicles in the frame.
        """
        results = []
        if not vehicles:
            return results

        for vehicle in vehicles:
            plate_res = self.detect_in_vehicle(frame, vehicle)
            if plate_res is not None:
                results.append(plate_res)

        return results
