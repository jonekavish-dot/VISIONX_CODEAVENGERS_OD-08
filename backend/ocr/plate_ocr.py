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
        """Return multi-contrast crops for white, yellow, shadowed, HSRP, and blurred plates."""
        if plate_crop is None or plate_crop.size == 0:
            return []
        h, w = plate_crop.shape[:2]
        
        # Upscale factor for optimal OCR resolution
        scale = max(3.5, 180.0 / max(1, h), 360.0 / max(1, w))
        resized = cv2.resize(
            plate_crop,
            (max(1, int(w * scale)), max(1, int(h * scale))),
            interpolation=cv2.INTER_CUBIC
        )
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY) if resized.ndim == 3 else resized
        
        # Variant 1: CLAHE + Bilateral Noise Filtering
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
        denoised = cv2.bilateralFilter(clahe, 5, 35, 35)
        
        # Variant 2: High Contrast Otsu Binarization
        otsu = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        
        # Variant 3: Adaptive Gaussian Thresholding
        adaptive = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 7
        )
        
        # Variant 4: Inverted Binarization (for dark background / yellow commercial plates)
        inverted = cv2.bitwise_not(otsu)
        
        # Variant 5: Unsharp Mask Sharpening
        kernel_sharp = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        sharpened = cv2.filter2D(denoised, -1, kernel_sharp)
        
        variants = [resized, denoised, otsu, adaptive, inverted, sharpened]
        
        # HSRP Left Strip Crop (removes blue IND band if plate is landscape)
        if w / max(1, h) >= 2.5:
            left_offset = int(resized.shape[1] * 0.12)
            if left_offset > 5:
                hsrp_crop = denoised[:, left_offset:]
                variants.append(hsrp_crop)

        return variants

    def recognize(self, plate_crop: np.ndarray) -> Dict[str, Any]:
        """
        Extracts license plate text from ROI using multi-variant binarization and slot-guided normalization.
        
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
                    
                    # Score quality: pattern-matched Indian registration > general format > raw text
                    quality = (3.0 if normalized else 0.0) + avg_confidence
                    candidates.append((quality, raw_text, avg_confidence, normalized))

            if not candidates:
                return {
                    "raw_text": "",
                    "normalized_text": None,
                    "ocr_confidence": 0.0
                }

            _, raw_text, avg_confidence, normalized_text = max(candidates, key=lambda item: item[0])
            
            # Boost confidence metric if slot repair achieved a verified Indian registration match
            final_conf = min(0.999, round(avg_confidence * (1.15 if normalized_text else 1.0), 3))

            return {
                "raw_text": raw_text,
                "normalized_text": normalized_text,
                "ocr_confidence": final_conf
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
        Normalize plate string with extreme precision using positional slot disambiguation.
        Does NOT blindly replace characters across the whole string.
        Applies slot-specific rules for Indian Registration (State Code + RTO Code + Series + Serial Number).
        """
        minimum_confidence = max(0.12, self.conf_thresh * 0.50)

        # Step 1: Pre-clean raw text
        cleaned_raw = raw_text.upper()
        
        # Remove common background/country codes ('IND', 'INDIA', 'IN')
        cleaned_raw = re.sub(r'\b(IND|INDIA)\b', '', cleaned_raw)
        cleaned = re.sub(r'[^A-Z0-9]', '', cleaned_raw)

        if confidence < minimum_confidence or len(cleaned) < 4 or len(cleaned) > 12:
            return None

        # Pattern 1: Direct Match for Standard Indian Format (e.g. TN01AB1234, MH12DE1433)
        std_match = re.match(r'^([A-Z]{2})(\d{2})([A-Z]{1,2})(\d{4})$', cleaned)
        if std_match:
            state = std_match.group(1)
            if state in self.INDIAN_STATE_CODES:
                return cleaned

        # Pattern 2: Bharat Series (BH) Format (e.g., 22BH1234A)
        bh_match = re.match(r'^(\d{2})BH(\d{4})([A-Z]{1,2})$', cleaned)
        if bh_match:
            return cleaned

        # Pattern 3: Standard 9-character format (e.g., TN1AB1234)
        std_9_match = re.match(r'^([A-Z]{2})(\d{1})([A-Z]{1,2})(\d{4})$', cleaned)
        if std_9_match:
            state = std_9_match.group(1)
            if state in self.INDIAN_STATE_CODES:
                return cleaned

        # Step 2: Slot-Based Positional Disambiguation Repair Engine
        # Handles typical OCR character confusion (e.g., 'O' vs '0', 'I' vs '1', 'S' vs '5', 'B' vs '8', 'Z' vs '2')
        alpha_to_digit = {'O': '0', 'D': '0', 'Q': '0', 'I': '1', 'L': '1', 'Z': '2', 'S': '5', 'B': '8', 'G': '6', 'T': '7'}
        digit_to_alpha = {'0': 'O', '1': 'I', '2': 'Z', '5': 'S', '8': 'B', '6': 'G', '7': 'T'}

        # Attempt Positional Repair for 9-10 Character Strings
        if 8 <= len(cleaned) <= 11:
            chars = list(cleaned)

            # Slot 0-1: State Code (MUST be Alphabetic)
            if chars[0] in digit_to_alpha: chars[0] = digit_to_alpha[chars[0]]
            if chars[1] in digit_to_alpha: chars[1] = digit_to_alpha[chars[1]]
            possible_state = f"{chars[0]}{chars[1]}"

            if possible_state in self.INDIAN_STATE_CODES:
                # Slot 2-3: RTO Code (MUST be Numeric)
                if len(chars) >= 10:
                    if chars[2] in alpha_to_digit: chars[2] = alpha_to_digit[chars[2]]
                    if chars[3] in alpha_to_digit: chars[3] = alpha_to_digit[chars[3]]

                    # Slot 4-5: Series (Can be 1 or 2 Alphabetic characters)
                    # Slot 6-9: Number (Last 4 MUST be Numeric)
                    for i in range(len(chars) - 4, len(chars)):
                        if chars[i] in alpha_to_digit:
                            chars[i] = alpha_to_digit[chars[i]]

                    # If middle series character was misread as digit, repair to alpha
                    if len(chars) == 10:
                        if chars[4] in digit_to_alpha and not chars[4].isalpha():
                            chars[4] = digit_to_alpha[chars[4]]

                    candidate = "".join(chars)
                    re_check = re.match(r'^([A-Z]{2})(\d{2})([A-Z]{1,2})(\d{4})$', candidate)
                    if re_check:
                        return candidate

                elif len(chars) == 9:
                    # RTO Code has 1 digit
                    if chars[2] in alpha_to_digit: chars[2] = alpha_to_digit[chars[2]]
                    for i in range(len(chars) - 4, len(chars)):
                        if chars[i] in alpha_to_digit:
                            chars[i] = alpha_to_digit[chars[i]]
                    candidate = "".join(chars)
                    re_check = re.match(r'^([A-Z]{2})(\d{1})([A-Z]{1,2})(\d{4})$', candidate)
                    if re_check:
                        return candidate

        # Step 3: Regex Search for Embedded Registration Patterns in Raw Text
        plate_pattern = r'([A-Z01586]{2})[\s\-]*([0-9ODQISZBT]{1,2})[\s\-]*([A-Z01586]{1,2})[\s\-]*([0-9ODQISZBT]{4})'
        match = re.search(plate_pattern, raw_text.upper())
        if match:
            raw_state, raw_rto, raw_series, raw_num = match.groups()
            
            # Disambiguate state
            s0 = digit_to_alpha.get(raw_state[0], raw_state[0])
            s1 = digit_to_alpha.get(raw_state[1], raw_state[1])
            state_candidate = f"{s0}{s1}"

            if state_candidate in self.INDIAN_STATE_CODES:
                clean_rto = "".join(alpha_to_digit.get(c, c) for c in raw_rto)
                clean_num = "".join(alpha_to_digit.get(c, c) for c in raw_num)
                clean_series = "".join(digit_to_alpha.get(c, c) if not c.isalpha() else c for c in raw_series)
                return f"{state_candidate}{clean_rto}{clean_series}{clean_num}"

        # If string is clean alphanumeric and length is valid
        if re.match(r'^[A-Z0-9]{5,11}$', cleaned):
            return cleaned

        return None
