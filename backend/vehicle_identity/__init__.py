from backend.vehicle_identity.feature_extractor import VehicleFeatureExtractor
from backend.vehicle_identity.similarity import cosine_similarity
from backend.vehicle_identity.identity_rules import evaluate_identity_decision
from backend.vehicle_identity.identity_service import VehicleIdentityService
from backend.vehicle_identity.schemas import (
    IdentityEventType,
    VehicleIdentity,
    IdentityObservation,
    IdentityMatchResult
)

__all__ = [
    "VehicleFeatureExtractor",
    "cosine_similarity",
    "evaluate_identity_decision",
    "VehicleIdentityService",
    "IdentityEventType",
    "VehicleIdentity",
    "IdentityObservation",
    "IdentityMatchResult"
]
