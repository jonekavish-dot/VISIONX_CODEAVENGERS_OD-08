"""
IVACS V-TRACE License Plate OCR Engine
Uses EasyOCR for character extraction with strict preservation of raw OCR output
and disciplined, non-destructive normalization for Indian & international formats.
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple
import numpy as np
import cv2
import easyocr
import torch
from backend.config import OCR_CONF_THRESHOLD

logger = logging.getLogger("vtrace.plate_ocr")

class PlateOCR:
    """Optical Character Recognition for license plate crops using EasyOCR."""

    # Valid Indian State/UT Codes
    INDIAN_STATE_CODES = {
        "AN", "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "DN",
        "GA", "GJ", "HP", "HR", "JH", "JK", "KA", "KL", "LA", "LD",
        "MH", "ML", "MN", "MP", "MZ", "NL", "OD", "PB", "PY", "RJ",
        "SK", "TN", "TR", "TS", "UK", "UP", "WB"
    }

    def __init__(self, languages: list = None, conf_thresh: float = OCR_CONF_THRESHOLD):
        self.conf_thresh = conf_thresh
        self.languages = languages or ['en']
        self.use_gpu = torch.cuda.is_available()
        logger.info(f"Initializing EasyOCR reader (gpu={self.use_gpu}, languages={self.languages})")
        self.reader = easyocr.Reader(self.languages, gpu=self.use_gpu)

    def preprocess_plate(self, plate_crop: np.ndarray) -> np.ndarray:
        """Enhance plate crop contrast and resolution for OCR readability."""
        if plate_crop is None or plate_crop.size == 0:
            return plate_crop

        h, w = plate_crop.shape[:2]
        # Upscale if the crop is small
        if h < 50 or w < 120:
            scale = max(2.0, 60.0 / max(1, h))
            plate_crop = cv2.resize(plate_crop, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY) if len(plate_crop.shape) == 3 else plate_crop
        
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Bilateral filter to smooth noise while keeping character edges sharp
        filtered = cv2.bilateralFilter(enhanced, 7, 50, 50)
        return filtered

    def _preprocess_variants(self, plate_crop: np.ndarray) -> list:
        """Return complementary crops for white, yellow, shadowed, and blurred plates."""
        if plate_crop is None or plate_crop.size == 0:
            return []
        h, w = plate_crop.shape[:2]
        scale = max(3.0, 160.0 / max(1, h), 320.0 / max(1, w))
        resized = cv2.resize(
            plate_crop,
            (max(1, int(w * scale)), max(1, int(h * scale))),
            interpolation=cv2.INTER_CUBIC
        )
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY) if resized.ndim == 3 else resized
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)
        denoised = cv2.bilateralFilter(clahe, 5, 35, 35)
        otsu = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        adaptive = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 7
        )
        return [resized, denoised, otsu, adaptive]

    def recognize(self, plate_crop: np.ndarray) -> Dict[str, Any]:
        """
        Extracts license plate text from ROI.
        
        Returns:
            Dict containing:
            {
                'raw_text': str,
                'normalized_text': Optional[str],
                'ocr_confidence': float
            }
        """
        if plate_crop is None or not isinstance(plate_crop, np.ndarray) or plate_crop.size == 0:
            return {
                "raw_text": "",
                "normalized_text": None,
                "ocr_confidence": 0.0
            }

        try:
            candidates = []
            for variant in self._preprocess_variants(plate_crop):
                # Restrict OCR to registration characters. This removes common
                # background detections from vehicle bumpers and signs.
                results = self.reader.readtext(
                    variant,
                    detail=1,
                    paragraph=False,
                    allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
                )
                if not results:
                    continue
                results.sort(key=lambda item: item[0][0][0])
                pieces = [item[1].strip() for item in results if item[1].strip()]
                confidences = [float(item[2]) for item in results if item[1].strip()]
                if pieces:
                    raw_text = " ".join(pieces)
                    avg_confidence = float(np.mean(confidences))
                    normalized = self._normalize_plate(raw_text, avg_confidence)
                    # Prefer a structurally valid Indian registration over a
                    # higher-confidence noise result.
                    quality = (2.0 if normalized else 0.0) + avg_confidence
                    candidates.append((quality, raw_text, avg_confidence, normalized))

            if not candidates:
                return {
                    "raw_text": "",
                    "normalized_text": None,
                    "ocr_confidence": 0.0
                }

            _, raw_text, avg_confidence, normalized_text = max(candidates, key=lambda item: item[0])

            return {
                "raw_text": raw_text,
                "normalized_text": normalized_text,
                "ocr_confidence": round(avg_confidence, 3)
            }

        except Exception as e:
            logger.error(f"Error during OCR recognition: {e}")
            return {
                "raw_text": "",
                "normalized_text": None,
                "ocr_confidence": 0.0
            }

    def _normalize_plate(self, raw_text: str, confidence: float) -> Optional[str]:
        """
        Normalize plate string with care.
        DO NOT blindly replace characters across the whole string.
        If OCR confidence is too low or plate format is fundamentally unreadable,
        returns None rather than hallucinating.
        """
        # A structurally valid Indian plate is useful even when CCTV quality
        # lowers EasyOCR confidence. Invalid short strings remain rejected.
        minimum_confidence = max(0.15, self.conf_thresh * 0.60)

        # Step 1: Search for Indian license plate pattern within raw text (ignoring noise tokens like 'IND', 'Ui em')
        plate_pattern = r'([A-Z]{2})[\s\-]*([0-9OD]{2})[\s\-]*([A-Z]{1,2})[\s\-]*([0-9OISZB]{4})'
        pattern_match = re.search(plate_pattern, raw_text.upper())
        if pattern_match:
            state, rto, series, num = pattern_match.groups()
            if state in self.INDIAN_STATE_CODES and confidence >= minimum_confidence:
                digit_map = {'O': '0', 'D': '0', 'I': '1', 'S': '5', 'Z': '2', 'B': '8'}
                clean_rto = ''.join(digit_map.get(c, c) for c in rto)
                clean_num = ''.join(digit_map.get(c, c) for c in num)
                return f"{state}{clean_rto}{series}{clean_num}"

        # Strip symbols, retain uppercase alphanumeric
        cleaned = re.sub(r'[^A-Za-z0-9]', '', raw_text).upper()

        # Strip blue/left 'IND' or 'IN' country code identifier commonly read by OCR
        if cleaned.startswith("IND") and len(cleaned) >= 11:
            cleaned = cleaned[3:]
        elif cleaned.startswith("IN") and len(cleaned) >= 11:
            cleaned = cleaned[2:]
        
        # Valid vehicle registration strings typically have between 4 and 11 alphanumeric characters
        if confidence < minimum_confidence or len(cleaned) < 4 or len(cleaned) > 12:
            return None

        # Pattern 2: Cleaned Indian Format
        indian_10_match = re.match(r'^([A-Z]{2})(\d{2})([A-Z]{1,2})(\d{4})$', cleaned)
        if indian_10_match:
            state, rto, series, num = indian_10_match.groups()
            if state in self.INDIAN_STATE_CODES:
                return f"{state}{rto}{series}{num}"
            return cleaned

        # Targeted positional character disambiguation ONLY for 9-10 character sequences
        if 8 <= len(cleaned) <= 10:
            candidate = list(cleaned)
            # Position 0, 1: State code letters (e.g. 0 -> O, 1 -> I)
            if candidate[0] == '0': candidate[0] = 'O'
            if candidate[1] == '0': candidate[1] = 'O'
            if candidate[0] == '1': candidate[0] = 'I'
            if candidate[1] == '1': candidate[1] = 'I'

            # Position 2, 3: RTO Digits (e.g. O -> 0, I -> 1, Z -> 2, S -> 5)
            digit_replacements = {'O': '0', 'D': '0', 'I': '1', 'Z': '2', 'S': '5', 'B': '8'}
            if candidate[2] in digit_replacements:
                candidate[2] = digit_replacements[candidate[2]]
            if candidate[3] in digit_replacements:
                candidate[3] = digit_replacements[candidate[3]]

            # Last 4 characters should be digits
            for i in range(len(candidate) - 4, len(candidate)):
                if candidate[i] in digit_replacements:
                    candidate[i] = digit_replacements[candidate[i]]

            candidate_str = "".join(candidate)
            test_match = re.match(r'^([A-Z]{2})(\d{2})([A-Z]{1,2})(\d{4})$', candidate_str)
            if test_match:
                state = test_match.group(1)
                if state in self.INDIAN_STATE_CODES:
                    return candidate_str

        # If it is clean alphanumeric of reasonable length and confidence >= threshold:
        if re.match(r'^[A-Z0-9]{5,11}$', cleaned):
            return cleaned

        # Otherwise uncertain -> return None as per instructions
        return None
