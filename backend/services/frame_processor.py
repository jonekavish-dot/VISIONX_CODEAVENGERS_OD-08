"""
IVACS V-TRACE Frame Processing Pipeline
Coordinates: Frame -> Vehicle Detection -> Plate Detection -> OCR -> Association -> Evidence Storage -> Database.
"""

import os
import cv2
import logging
import numpy as np
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any

from backend.config import EVIDENCE_DIR, CAMERAS, DEFAULT_CAMERA_ID
from backend.schemas.detection import DetectionEvent, ProcessingStatus
from backend.detection.vehicle_detector import VehicleDetector
from backend.detection.plate_detector import PlateDetector
from backend.ocr.plate_ocr import PlateOCR
from backend.database.database import insert_detection

from backend.vehicle_identity.identity_service import VehicleIdentityService

logger = logging.getLogger("vtrace.frame_processor")

class FrameProcessor:
    """End-to-end video frame processor for IVACS V-TRACE."""

    def __init__(
        self,
        vehicle_detector: Optional[VehicleDetector] = None,
        plate_detector: Optional[PlateDetector] = None,
        ocr_engine: Optional[PlateOCR] = None,
        identity_service: Optional[VehicleIdentityService] = None
    ):
        self.vehicle_detector = vehicle_detector or VehicleDetector()
        self.plate_detector = plate_detector or PlateDetector()
        self.ocr_engine = ocr_engine or PlateOCR()
        self.identity_service = identity_service or VehicleIdentityService()
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    def process_frame(
        self,
        frame: np.ndarray,
        frame_number: int,
        camera_id: str = DEFAULT_CAMERA_ID,
        save_evidence: bool = True
    ) -> Tuple[List[DetectionEvent], np.ndarray]:
        """
        Executes the full pipeline for a single frame.
        
        Returns:
            (events: List[DetectionEvent], annotated_frame: np.ndarray)
        """
        now_dt = datetime.now()
        timestamp_iso = now_dt.isoformat()
        timestamp_slug = now_dt.strftime("%Y%m%d_%H%M%S_%f")[:19]
        zone = CAMERAS.get(camera_id, CAMERAS[DEFAULT_CAMERA_ID]).zone

        # Guard against corrupt or empty frame
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            dummy_event = DetectionEvent(
                camera_id=camera_id,
                zone=zone,
                timestamp=timestamp_iso,
                frame_number=frame_number,
                status=ProcessingStatus.ERROR
            )
            return [dummy_event], np.zeros((100, 100, 3), dtype=np.uint8)

        annotated_frame = frame.copy()
        events: List[DetectionEvent] = []

        try:
            # 1. VEHICLE DETECTION
            vehicles = self.vehicle_detector.detect(frame, frame_number=frame_number)
            
            if not vehicles:
                # Clean failure handling: NO_VEHICLE
                no_veh_event = DetectionEvent(
                    camera_id=camera_id,
                    zone=zone,
                    timestamp=timestamp_iso,
                    frame_number=frame_number,
                    status=ProcessingStatus.NO_VEHICLE
                )
                self._draw_overlay_header(annotated_frame, camera_id, zone, frame_number, "NO VEHICLE DETECTED")
                return [no_veh_event], annotated_frame

            # Process each detected vehicle
            for v_idx, vehicle in enumerate(vehicles):
                vx1, vy1, vx2, vy2 = vehicle["vehicle_bbox"]
                v_class = vehicle["vehicle_class"]
                v_conf = vehicle["vehicle_confidence"]
                
                # Crop vehicle for evidence
                vh, vw = frame.shape[:2]
                cvx1, cvy1 = max(0, vx1), max(0, vy1)
                cvx2, cvy2 = min(vw, vx2), min(vh, vy2)
                vehicle_crop = frame[cvy1:cvy2, cvx1:cvx2]

                # 2. PLATE DETECTION & ASSOCIATION
                plate_result = self.plate_detector.detect_in_vehicle(frame, vehicle)

                if not plate_result:
                    # Preserve vehicle evidence and identity history even when
                    # localization fails. A missing plate must not discard the
                    # vehicle observation or its cropped image.
                    prefix = f"{camera_id}_{timestamp_slug}_f{frame_number}_v{v_idx}"
                    vehicle_crop_path = None
                    frame_path = None
                    annotated_path = None
                    if save_evidence and vehicle_crop.size > 0:
                        frame_path = str(EVIDENCE_DIR / f"{prefix}_frame.jpg")
                        vehicle_crop_path = str(EVIDENCE_DIR / f"{prefix}_vehicle.jpg")
                        annotated_path = str(EVIDENCE_DIR / f"{prefix}_annotated.jpg")
                        try:
                            cv2.imwrite(frame_path, frame)
                            cv2.imwrite(vehicle_crop_path, vehicle_crop)
                            self._draw_vehicle_box(annotated_frame, vx1, vy1, vx2, vy2, v_class, v_conf)
                            cv2.imwrite(annotated_path, annotated_frame)
                        except Exception as err:
                            logger.error(f"Failed to save no-plate evidence images: {err}")

                    id_result = None
                    if self.identity_service and vehicle_crop.size > 0:
                        try:
                            id_result = self.identity_service.process_vehicle(
                                vehicle_crop=vehicle_crop,
                                observed_plate=None,
                                plate_confidence=None,
                                ocr_confidence=0.0,
                                vehicle_class=v_class,
                                camera_id=camera_id,
                                zone=zone,
                                frame_number=frame_number,
                                timestamp=timestamp_iso,
                                vehicle_crop_path=vehicle_crop_path,
                                plate_crop_path=None,
                                frame_path=frame_path
                            )
                        except Exception as id_err:
                            logger.error(f"Error recording no-plate vehicle on frame {frame_number}: {id_err}")

                    # Clean failure handling: NO_PLATE
                    event = DetectionEvent(
                        camera_id=camera_id,
                        zone=zone,
                        timestamp=timestamp_iso,
                        frame_number=frame_number,
                        status=ProcessingStatus.NO_PLATE,
                        vehicle_class=v_class,
                        vehicle_confidence=v_conf,
                        vehicle_bbox=[vx1, vy1, vx2, vy2],
                        vehicle_crop_path=vehicle_crop_path,
                        frame_path=frame_path,
                        annotated_frame_path=annotated_path,
                        vehicle_id=id_result.vehicle_id if id_result else None,
                        visual_similarity=id_result.similarity if id_result else None,
                        identity_event=id_result.event_type.value if id_result else None,
                        identity_match_status=(
                            "MATCHED" if id_result and id_result.matched
                            else "UNMATCHED" if id_result else None
                        )
                    )
                    self._draw_vehicle_box(annotated_frame, vx1, vy1, vx2, vy2, v_class, v_conf)
                    try:
                        insert_detection(event)
                    except Exception as db_err:
                        logger.error(f"Error persisting no-plate detection: {db_err}")
                    events.append(event)
                    continue

                plate_bbox = plate_result["plate_bbox"]
                plate_conf = plate_result["plate_detection_confidence"]
                plate_crop = plate_result["plate_crop"]
                px1, py1, px2, py2 = plate_bbox

                # 3. OCR EXTRACTION
                ocr_res = self.ocr_engine.recognize(plate_crop)
                raw_plate = ocr_res["raw_text"]
                norm_plate = ocr_res["normalized_text"]
                ocr_conf = ocr_res["ocr_confidence"]

                # Determine status
                if not raw_plate:
                    status = ProcessingStatus.PLATE_UNREADABLE
                else:
                    status = ProcessingStatus.DETECTED

                # 4. DRAW OVERLAYS
                self._draw_vehicle_box(annotated_frame, vx1, vy1, vx2, vy2, v_class, v_conf)
                display_text = norm_plate or raw_plate or "PLATE"
                self._draw_plate_box(annotated_frame, px1, py1, px2, py2, display_text, ocr_conf)

                # 5. EVIDENCE STORAGE
                vehicle_crop_path = None
                plate_crop_path = None
                frame_path = None
                annotated_path = None

                if save_evidence and status in [ProcessingStatus.DETECTED, ProcessingStatus.PLATE_UNREADABLE]:
                    prefix = f"{camera_id}_{timestamp_slug}_f{frame_number}_v{v_idx}"
                    
                    frame_path = str(EVIDENCE_DIR / f"{prefix}_frame.jpg")
                    vehicle_crop_path = str(EVIDENCE_DIR / f"{prefix}_vehicle.jpg")
                    plate_crop_path = str(EVIDENCE_DIR / f"{prefix}_plate.jpg")
                    annotated_path = str(EVIDENCE_DIR / f"{prefix}_annotated.jpg")

                    try:
                        cv2.imwrite(frame_path, frame)
                        if vehicle_crop.size > 0:
                            cv2.imwrite(vehicle_crop_path, vehicle_crop)
                        if plate_crop.size > 0:
                            cv2.imwrite(plate_crop_path, plate_crop)
                        cv2.imwrite(annotated_path, annotated_frame)
                    except Exception as err:
                        logger.error(f"Failed to save evidence images: {err}")

                # 6. VEHICLE VISUAL FINGERPRINT & IDENTITY MATCHING
                id_result = None
                if self.identity_service and vehicle_crop.size > 0:
                    try:
                        id_result = self.identity_service.process_vehicle(
                            vehicle_crop=vehicle_crop,
                            observed_plate=norm_plate or raw_plate,
                            plate_confidence=plate_conf,
                            ocr_confidence=ocr_conf,
                            vehicle_class=v_class,
                            camera_id=camera_id,
                            zone=zone,
                            frame_number=frame_number,
                            timestamp=timestamp_iso,
                            vehicle_crop_path=vehicle_crop_path,
                            plate_crop_path=plate_crop_path,
                            frame_path=frame_path
                        )
                    except Exception as id_err:
                        logger.error(f"Error in identity service on frame {frame_number}: {id_err}")

                v_id = id_result.vehicle_id if id_result else None
                v_sim = id_result.similarity if id_result else None
                v_evt = id_result.event_type.value if id_result else None
                v_match = "MATCHED" if (id_result and id_result.matched) else ("UNMATCHED" if id_result else None)

                # 7. STRUCTURED DETECTION EVENT
                event = DetectionEvent(
                    camera_id=camera_id,
                    zone=zone,
                    timestamp=timestamp_iso,
                    frame_number=frame_number,
                    status=status,
                    vehicle_class=v_class,
                    vehicle_confidence=v_conf,
                    vehicle_bbox=[vx1, vy1, vx2, vy2],
                    plate=norm_plate,
                    raw_plate=raw_plate,
                    plate_confidence=plate_conf,
                    ocr_confidence=ocr_conf,
                    plate_bbox=[px1, py1, px2, py2],
                    vehicle_crop_path=vehicle_crop_path,
                    plate_crop_path=plate_crop_path,
                    frame_path=frame_path,
                    annotated_frame_path=annotated_path,
                    vehicle_id=v_id,
                    visual_similarity=v_sim,
                    identity_event=v_evt,
                    identity_match_status=v_match
                )

                # 7. PERSIST TO SQLITE
                try:
                    event_id = insert_detection(event)
                    event.id = event_id
                except Exception as db_err:
                    logger.error(f"Error persisting detection to SQLite: {db_err}")

                events.append(event)

            self._draw_overlay_header(
                annotated_frame, camera_id, zone, frame_number,
                f"VEHICLES: {len(vehicles)} | DETECTIONS: {sum(1 for e in events if e.status == ProcessingStatus.DETECTED)}"
            )

        except Exception as ex:
            logger.error(f"Unexpected error in frame_processor on frame {frame_number}: {ex}", exc_info=True)
            err_event = DetectionEvent(
                camera_id=camera_id,
                zone=zone,
                timestamp=timestamp_iso,
                frame_number=frame_number,
                status=ProcessingStatus.ERROR
            )
            events.append(err_event)

        return events, annotated_frame

    def _draw_vehicle_box(self, img: np.ndarray, x1: int, y1: int, x2: int, y2: int, v_class: str, conf: float):
        # Green bounding box for vehicle
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"VEHICLE: {v_class.upper()} {conf:.2f}"
        (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(img, (x1, max(0, y1 - 20)), (x1 + w, y1), (0, 255, 0), -1)
        cv2.putText(img, label, (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

    def _draw_plate_box(self, img: np.ndarray, x1: int, y1: int, x2: int, y2: int, plate_text: str, conf: float):
        # Yellow/Cyan box for license plate
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 255), 2)
        label = f"PLATE: {plate_text} (OCR: {conf:.2f})"
        (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(img, (x1, max(0, y1 - 20)), (x1 + w, y1), (0, 255, 255), -1)
        cv2.putText(img, label, (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

    def _draw_overlay_header(self, img: np.ndarray, camera_id: str, zone: str, frame_num: int, extra: str = ""):
        header_text = f"IVACS V-TRACE | {camera_id} ({zone}) | F#{frame_num} | {extra}"
        cv2.rectangle(img, (0, 0), (img.shape[1], 28), (20, 24, 33), -1)
        cv2.putText(img, header_text, (10, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
