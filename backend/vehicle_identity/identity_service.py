"""
IVACS V-TRACE Vehicle Identity Service
Manages persistent visual fingerprints, cosine similarity matching,
decision rule evaluation, and observation logging.
"""

import logging
import json
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import numpy as np

from backend.config import IDENTITY_HIGH_THRESHOLD, IDENTITY_LOW_THRESHOLD
from backend.vehicle_identity.feature_extractor import VehicleFeatureExtractor
from backend.vehicle_identity.similarity import cosine_similarity
from backend.vehicle_identity.identity_rules import evaluate_identity_decision
from backend.vehicle_identity.schemas import (
    VehicleIdentity,
    IdentityObservation,
    IdentityEventType,
    IdentityMatchResult
)
from backend.database.database import (
    get_all_vehicle_identities,
    get_vehicle_identity_by_id,
    get_vehicle_identity_by_plate,
    get_next_vehicle_id,
    insert_vehicle_identity,
    update_vehicle_identity,
    insert_identity_observation,
    get_identity_observations_for_vehicle
)

logger = logging.getLogger("vtrace.identity_service")

class VehicleIdentityService:
    """Orchestrates vehicle visual fingerprinting, matching, and lifecycle persistence."""

    def __init__(self, feature_extractor: Optional[VehicleFeatureExtractor] = None):
        self.feature_extractor = feature_extractor or VehicleFeatureExtractor()
        # In-memory cache of VehicleIdentity records for fast cosine comparisons
        self._identities: List[VehicleIdentity] = []
        self._refresh_cache()

    def _refresh_cache(self):
        try:
            self._identities = get_all_vehicle_identities()
        except Exception as e:
            logger.error(f"Failed to refresh vehicle identities cache: {e}")
            self._identities = []

    def process_vehicle(
        self,
        vehicle_crop: np.ndarray,
        observed_plate: Optional[str] = None,
        plate_confidence: Optional[float] = None,
        ocr_confidence: Optional[float] = None,
        vehicle_class: Optional[str] = None,
        camera_id: str = "CAM-01",
        zone: str = "GATE_IN",
        frame_number: int = 0,
        timestamp: Optional[str] = None,
        vehicle_crop_path: Optional[str] = None,
        plate_crop_path: Optional[str] = None,
        frame_path: Optional[str] = None
    ) -> IdentityMatchResult:
        """
        Processes a vehicle crop against known identities:
        1. Extracts 512-dim embedding
        2. Computes cosine similarity with candidates
        3. Applies deterministic identity rules
        4. Updates or creates identity in SQLite
        5. Logs observation and returns IdentityMatchResult
        """
        now_iso = timestamp or datetime.now().isoformat()
        clean_plate = observed_plate.strip().upper() if observed_plate else None

        # 1. Extract embedding
        feat_res = self.feature_extractor.extract(vehicle_crop)
        embedding = feat_res["embedding"]

        # 2. Search candidates in cache
        best_candidate: Optional[VehicleIdentity] = None
        best_similarity = 0.0
        plate_match_candidate: Optional[VehicleIdentity] = None
        plate_match_sim = 0.0

        for cand in self._identities:
            if not cand.embedding:
                continue
            sim = cosine_similarity(embedding, cand.embedding)
            
            # Track candidate with same plate
            if clean_plate and cand.canonical_plate == clean_plate:
                if plate_match_candidate is None or sim > plate_match_sim:
                    plate_match_candidate = cand
                    plate_match_sim = sim

            # Track highest visual match overall
            if sim > best_similarity:
                best_similarity = sim
                best_candidate = cand

        # 3. Determine primary candidate to compare against
        # If plate matches an identity, prioritize that candidate for Rule A & Rule B
        if plate_match_candidate is not None:
            active_candidate = plate_match_candidate
            eval_sim = plate_match_sim
            cand_plate = plate_match_candidate.canonical_plate
        elif best_candidate is not None and best_similarity >= IDENTITY_HIGH_THRESHOLD:
            # High visual match with a candidate having a different or null plate (Rule C or D)
            active_candidate = best_candidate
            eval_sim = best_similarity
            cand_plate = best_candidate.canonical_plate
        else:
            active_candidate = best_candidate
            eval_sim = best_similarity
            cand_plate = best_candidate.canonical_plate if best_candidate else None

        # 4. Evaluate decision rules
        event_type, details = evaluate_identity_decision(
            observed_plate=clean_plate,
            candidate_plate=cand_plate,
            visual_similarity=eval_sim,
            high_threshold=IDENTITY_HIGH_THRESHOLD,
            low_threshold=IDENTITY_LOW_THRESHOLD
        )

        # 5. Persist / Update Identity
        assigned_vehicle_id: str = ""
        prev_crop_path: Optional[str] = None

        if event_type in [IdentityEventType.SAME_VEHICLE, IdentityEventType.PLATE_UNREADABLE_VEHICLE_MATCH]:
            # Associate with existing candidate
            assigned_vehicle_id = active_candidate.vehicle_id
            new_visit_count = active_candidate.visit_count + 1
            
            # Fetch previous observation crop for evidence comparison
            prev_obs = get_identity_observations_for_vehicle(assigned_vehicle_id)
            if prev_obs:
                prev_crop_path = prev_obs[0].vehicle_crop_path

            # Update identity record
            update_vehicle_identity(
                vehicle_id=assigned_vehicle_id,
                last_seen=now_iso,
                visit_count=new_visit_count,
                canonical_plate=clean_plate or active_candidate.canonical_plate,
                embedding=embedding
            )
            # Update local cache
            active_candidate.last_seen = now_iso
            active_candidate.visit_count = new_visit_count
            if clean_plate:
                active_candidate.canonical_plate = clean_plate
            active_candidate.embedding = embedding

        else:
            # Create NEW vehicle identity (for NEW_VEHICLE, POSSIBLE_IDENTITY_MISMATCH, POSSIBLE_PLATE_SWAP)
            new_vid = get_next_vehicle_id()
            assigned_vehicle_id = new_vid
            
            if active_candidate and event_type in [IdentityEventType.POSSIBLE_IDENTITY_MISMATCH, IdentityEventType.POSSIBLE_PLATE_SWAP]:
                prev_obs = get_identity_observations_for_vehicle(active_candidate.vehicle_id)
                if prev_obs:
                    prev_crop_path = prev_obs[0].vehicle_crop_path

            new_identity = VehicleIdentity(
                vehicle_id=new_vid,
                canonical_plate=clean_plate,
                first_seen=now_iso,
                last_seen=now_iso,
                visit_count=1,
                vehicle_class=vehicle_class,
                embedding=embedding,
                created_at=now_iso,
                updated_at=now_iso
            )
            insert_vehicle_identity(new_identity)
            self._identities.append(new_identity)

        # 6. Record observation in database
        obs = IdentityObservation(
            vehicle_identity_id=assigned_vehicle_id,
            observed_plate=clean_plate,
            plate_confidence=plate_confidence,
            ocr_confidence=ocr_confidence,
            visual_similarity=round(eval_sim, 3),
            event_type=event_type,
            camera_id=camera_id,
            zone=zone,
            timestamp=now_iso,
            frame_number=frame_number,
            vehicle_crop_path=vehicle_crop_path,
            plate_crop_path=plate_crop_path,
            frame_path=frame_path,
            previous_crop_path=prev_crop_path
        )
        insert_identity_observation(obs)

        is_matched = (event_type in [IdentityEventType.SAME_VEHICLE, IdentityEventType.PLATE_UNREADABLE_VEHICLE_MATCH])

        return IdentityMatchResult(
            vehicle_id=assigned_vehicle_id,
            similarity=round(eval_sim, 3),
            matched=is_matched,
            event_type=event_type,
            previous_crop_path=prev_crop_path,
            canonical_plate=clean_plate,
            details=details
        )
