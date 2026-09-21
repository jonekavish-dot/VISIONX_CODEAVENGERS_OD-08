"""
IVACS V-TRACE Identity Decision Rules
Encapsulates all 5 deterministic identity decision rules (Rules A through E).
Provides analytical signals without non-verified claims.
"""

from typing import Optional, Tuple
from backend.config import IDENTITY_HIGH_THRESHOLD, IDENTITY_LOW_THRESHOLD
from backend.vehicle_identity.schemas import IdentityEventType

def evaluate_identity_decision(
    observed_plate: Optional[str],
    candidate_plate: Optional[str],
    visual_similarity: float,
    high_threshold: float = IDENTITY_HIGH_THRESHOLD,
    low_threshold: float = IDENTITY_LOW_THRESHOLD
) -> Tuple[IdentityEventType, str]:
    """
    Evaluates vehicle identity relationship according to deterministic decision rules:
    
    RULE A: Same plate + high visual similarity => SAME_VEHICLE
    RULE B: Same plate + low visual similarity  => POSSIBLE_IDENTITY_MISMATCH
    RULE C: Different plate + high visual similarity => POSSIBLE_PLATE_SWAP
    RULE D: No reliable plate + high visual similarity with known identity => PLATE_UNREADABLE_VEHICLE_MATCH
    RULE E: No historical match => NEW_VEHICLE
    """
    # Clean plates for comparison
    clean_obs = observed_plate.strip().upper() if observed_plate else None
    clean_cand = candidate_plate.strip().upper() if candidate_plate else None

    # Case 1: No historical candidate exists (RULE E)
    if clean_cand is None and visual_similarity <= 0.0:
        return (
            IdentityEventType.NEW_VEHICLE,
            "No historical match found; registered as new vehicle identity."
        )

    # Case 2: Observed plate is unreadable / None (RULE D or fallback E)
    if not clean_obs:
        if visual_similarity >= high_threshold:
            return (
                IdentityEventType.PLATE_UNREADABLE_VEHICLE_MATCH,
                f"UNDETECTED_PLATE_RECOVERED_VIA_VISUAL_REID: License plate obscured or unreadable, but 512-D deep visual fingerprint matched registered vehicle identity {clean_cand or 'known vehicle'} ({visual_similarity:.2f} similarity)."
            )
        else:
            return (
                IdentityEventType.NEW_VEHICLE,
                "Plate unreadable and no high visual match; registered as new vehicle identity."
            )

    # Case 3: Same plate observed as candidate identity
    if clean_cand and clean_obs == clean_cand:
        if visual_similarity >= high_threshold:
            # RULE A: Same plate + high visual similarity
            return (
                IdentityEventType.SAME_VEHICLE,
                f"Same plate and visual fingerprint is consistent with known vehicle ({visual_similarity:.2f} similarity)."
            )
        else:
            # RULE B: Same plate + low visual similarity
            return (
                IdentityEventType.POSSIBLE_IDENTITY_MISMATCH,
                f"POSSIBLE PLATE-VEHICLE MISMATCH: Observed vehicle appearance deviates significantly from historical vehicle associated with plate {clean_obs} ({visual_similarity:.2f} similarity)."
            )

    # Case 4: Different plate observed (or candidate registered under different plate)
    if clean_cand and clean_obs != clean_cand:
        if visual_similarity >= high_threshold:
            # RULE C: Different plate + high visual similarity
            return (
                IdentityEventType.POSSIBLE_PLATE_SWAP,
                f"POSSIBLE PLATE SWAP: Visual fingerprint strongly matches vehicle identity {clean_cand} ({visual_similarity:.2f} similarity) but carries different plate {clean_obs}."
            )
        else:
            # No conflict with candidate, new vehicle
            return (
                IdentityEventType.NEW_VEHICLE,
                f"New vehicle plate {clean_obs} observed with no conflicting visual fingerprint."
            )

    # Case 5: Fallback to RULE E
    return (
        IdentityEventType.NEW_VEHICLE,
        "No historical match found; registered as new vehicle identity."
    )
