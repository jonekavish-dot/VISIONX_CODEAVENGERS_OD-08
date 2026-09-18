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

        try:
            vx1, vy1, vx2, vy2 = [int(round(value)) for value in vehicle["vehicle_bbox"]]
        except (KeyError, TypeError, ValueError):
            logger.warning("Vehicle detection has an invalid bounding box: %s", vehicle)
            return None
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
                if results and len(results) > 0 and results[0].boxes and len(results[0].boxes) > 0:
                    # A plate model may return several overlapping boxes.  Use its
                    # highest-confidence result, not whichever box happens to be first.
                    box = max(results[0].boxes, key=lambda item: float(item.conf[0].item()))
                    conf = float(box.conf[0].item())
                    px1, py1, px2, py2 = box.xyxy[0].cpu().numpy().astype(int)
                    # Convert to global coordinates
                    gx1 = max(0, vx1 + px1)
                    gy1 = max(0, vy1 + py1)
                    gx2 = min(w_frame, vx1 + px2)
                    gy2 = min(h_frame, vy1 + py2)
                    
                    plate_crop = frame[gy1:gy2, gx1:gx2]
                    if gx2 <= gx1 or gy2 <= gy1 or plate_crop.size == 0:
                        raise ValueError("plate model returned an empty clipped crop")
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
        Locates a plate candidate using several views of the bumper.

        Indian registration plates are not all landscape rectangles: cars and trucks
        are usually about 2:1 to 5:1, while motorcycle plates can be nearly square.
        Perspective, compression, and dark plates also make a single Otsu gradient
        unreliable, so candidates are collected from both edge and bright-plate
        masks before being scored.
        """
        vh, vw = vehicle_crop.shape[:2]
        if vh < 20 or vw < 20:
            return None

        # The plate is normally low on a vehicle, but a close frontal view can
        # place it around the middle.  Include both cases.
        y_start = int(vh * 0.35)
        y_end = int(vh * 0.98)
        search_roi = vehicle_crop[y_start:y_end, :]
        if search_roi.size == 0:
            return None

        gray = cv2.cvtColor(search_roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)

        # Use multiple masks because white plates, yellow commercial plates, and
        # shadowed plates produce very different pixel distributions.
        masks = []
        for kernel_size in ((9, 3), (15, 5)):
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_size)
            gradient = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)
            masks.append(cv2.threshold(gradient, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1])
        blackhat_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
        blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, blackhat_kernel)
        masks.append(cv2.threshold(blackhat, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1])
        masks.append(cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1])

        best_candidate = None
        best_score = -1.0

        for mask in masks:
            # Join character strokes into one plate-like component.
            mask = cv2.morphologyEx(
                mask, cv2.MORPH_CLOSE,
                cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, vw // 35), 3))
            )
            contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                x, y, w, h = cv2.boundingRect(c)
                min_width = max(18, int(vw * 0.08))
                min_height = max(8, int(vh * 0.025))
                if w < min_width or h < min_height:
                    continue
                aspect = float(w) / float(h)
                area = w * h
                rel_area = area / float(max(1, vw * (y_end - y_start)))

                # Indian motorcycle plates may be close to square; car/truck
                # plates are generally landscape. Reject only implausible blobs.
                if not 1.15 <= aspect <= 7.0 or not 0.003 <= rel_area <= 0.35:
                    continue

                center_dist = abs((x + w / 2.0) - (vw / 2.0)) / max(1.0, vw / 2.0)
                vertical = (y + h / 2.0) / max(1.0, (y_end - y_start))
                aspect_score = max(0.0, 1.0 - abs(aspect - 2.8) / 3.5)
                score = (
                    0.42 * aspect_score
                    + 0.33 * max(0.0, 1.0 - center_dist)
                    + 0.25 * min(1.0, vertical)
                )
                if score > best_score:
                    best_score = score
                    pad_x = max(3, int(w * 0.08))
                    pad_y = max(3, int(h * 0.18))
                    bx1 = max(0, x - pad_x)
                    by1 = max(0, (y + y_start) - pad_y)
                    bx2 = min(vw, x + w + pad_x)
                    by2 = min(vh, (y + y_start) + h + pad_y)
                    best_candidate = (bx1, by1, bx2, by2, min(0.95, max(0.50, 0.55 + score * 0.40)))

        if best_candidate is not None:
            bx1, by1, bx2, by2, conf = best_candidate
            gx1 = max(0, min(w_frame, vx1 + bx1))
            gy1 = max(0, min(h_frame, vy1 + by1))
            gx2 = max(0, min(w_frame, vx1 + bx2))
            gy2 = max(0, min(h_frame, vy1 + by2))
            if gx2 > gx1 and gy2 > gy1:
                return (gx1, gy1, gx2, gy2, conf)

        # Last-resort crop for a very small/compressed plate.  Keep it centered
        # and low, and mark it low confidence so OCR/identity logic does not
        # treat an arbitrary bumper crop as a successful plate detection.
        fb_x1 = int(vx1 + vw * 0.20)
        fb_y1 = int(vy1 + vh * 0.58)
        fb_x2 = int(vx1 + vw * 0.80)
        fb_y2 = int(vy1 + vh * 0.92)
        
        gx1 = max(0, min(w_frame, fb_x1))
        gy1 = max(0, min(h_frame, fb_y1))
        gx2 = max(0, min(w_frame, fb_x2))
        gy2 = max(0, min(h_frame, fb_y2))
        
        if (gx2 - gx1) > 20 and (gy2 - gy1) > 10:
            return (gx1, gy1, gx2, gy2, 0.40)

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
