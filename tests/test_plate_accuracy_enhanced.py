"""
Tests for Enhanced 99.9% License Plate OCR Accuracy Engine
Validates slot-based positional disambiguation, multi-variant binarization,
HSRP IND strip removal, and state code validation.
"""

import pytest
import numpy as np
import cv2
from backend.ocr.plate_ocr import PlateOCR


@pytest.fixture
def plate_ocr():
    return PlateOCR()


def test_positional_slot_disambiguation_repair(plate_ocr):
    """Test positional slot repairs on typical OCR character misreadings."""
    
    # Test 1: 'O' instead of '0' in RTO code slot
    # Raw: TNO1AB1234 -> Normalized: TN01AB1234
    res1 = plate_ocr._normalize_plate("TNO1AB1234", 0.85)
    assert res1 == "TN01AB1234", f"Expected TN01AB1234, got {res1}"

    # Test 2: 'I' instead of '1' in RTO code slot and number slot
    # Raw: MHI2DEI433 -> Normalized: MH12DE1433
    res2 = plate_ocr._normalize_plate("MHI2DEI433", 0.85)
    assert res2 == "MH12DE1433", f"Expected MH12DE1433, got {res2}"

    # Test 3: 'O' instead of '0' in state slot (should keep state code) and RTO slot
    # Raw: KAO1AB1234 -> Normalized: KA01AB1234
    res3 = plate_ocr._normalize_plate("KAO1AB1234", 0.85)
    assert res3 == "KA01AB1234", f"Expected KA01AB1234, got {res3}"

    # Test 4: Bharat Series format preservation
    # Raw: 22BH1234A -> Normalized: 22BH1234A
    res4 = plate_ocr._normalize_plate("22BH1234A", 0.90)
    assert res4 == "22BH1234A", f"Expected 22BH1234A, got {res4}"

    # Test 5: 'Z' instead of '2' in numeric slot
    # Raw: DL01AB12Z4 -> Normalized: DL01AB1224
    res5 = plate_ocr._normalize_plate("DL01AB12Z4", 0.85)
    assert res5 == "DL01AB1224", f"Expected DL01AB1224, got {res5}"


def test_hsrp_ind_strip_and_raw_cleaning(plate_ocr):
    """Test stripping of background country codes and noisy HSRP prefixes."""
    # Raw text containing IND prefix
    res1 = plate_ocr._normalize_plate("IND TN01AB1234", 0.88)
    assert res1 == "TN01AB1234", f"Expected TN01AB1234, got {res1}"

    # Raw text containing INDIA prefix
    res2 = plate_ocr._normalize_plate("INDIA MH12DE1433", 0.88)
    assert res2 == "MH12DE1433", f"Expected MH12DE1433, got {res2}"


def test_preprocess_variants_generation(plate_ocr):
    """Test multi-contrast preprocessing variants generation."""
    dummy_crop = np.zeros((60, 200, 3), dtype=np.uint8)
    cv2.putText(dummy_crop, "TN01AB1234", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    variants = plate_ocr._preprocess_variants(dummy_crop)
    # Should generate at least 6 variants (resized, denoised, otsu, adaptive, inverted, sharpened, + hsrp)
    assert len(variants) >= 6
    for var in variants:
        assert isinstance(var, np.ndarray)
        assert var.shape[0] > 0 and var.shape[1] > 0


def test_invalid_and_low_confidence_filtering(plate_ocr):
    """Test rejection of noisy/short/low-confidence text."""
    assert plate_ocr._normalize_plate("A1", 0.95) is None
    assert plate_ocr._normalize_plate("TN01AB1234", 0.05) is None
    assert plate_ocr._normalize_plate("INVALIDTEXTTHATISTOOLONG123456789", 0.95) is None
