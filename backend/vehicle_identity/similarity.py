"""
IVACS V-TRACE Visual Fingerprint Similarity Engine
Calculates normalized cosine similarity between vehicle visual feature embeddings.
"""

from typing import Union, List, Sequence
import numpy as np

def cosine_similarity(
    a: Union[Sequence[float], np.ndarray],
    b: Union[Sequence[float], np.ndarray]
) -> float:
    """
    Computes cosine similarity between two feature vectors.
    Returns a float clamped between 0.0 and 1.0.
    """
    if a is None or b is None:
        return 0.0

    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)

    if va.size == 0 or vb.size == 0 or va.shape != vb.shape:
        return 0.0

    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)

    if norm_a < 1e-7 or norm_b < 1e-7:
        return 0.0

    sim = float(np.dot(va, vb) / (norm_a * norm_b))
    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, sim))
