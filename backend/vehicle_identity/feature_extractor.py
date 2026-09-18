"""
IVACS V-TRACE Vehicle Visual Feature Extractor
Extracts 512-dimensional L2-normalized feature embeddings from vehicle crops
using a pretrained torchvision ResNet18 backbone. Cached once in memory.
"""

import logging
from typing import Dict, Any, Optional, List
import numpy as np
import cv2
import torch
import torchvision.models as models

logger = logging.getLogger("vtrace.feature_extractor")

class VehicleFeatureExtractor:
    """Extracts visual appearance embeddings from vehicle image crops."""

    def __init__(self, device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Loading ResNet18 feature extractor on device: {self.device}")
        
        # Load pretrained ResNet18
        self.model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        # Replace 1000-class classification head with identity to get 512-dim embedding
        self.model.fc = torch.nn.Identity()
        self.model.to(self.device)
        self.model.eval()

        # ImageNet normalization constants
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def extract(self, vehicle_crop: np.ndarray) -> Dict[str, Any]:
        """
        Extracts L2-normalized visual fingerprint from a vehicle crop.
        
        Returns:
            Dict:
            {
                "embedding": List[float],
                "dimension": int,
                "quality": float
            }
        """
        if vehicle_crop is None or not isinstance(vehicle_crop, np.ndarray) or vehicle_crop.size == 0:
            return {
                "embedding": [0.0] * 512,
                "dimension": 512,
                "quality": 0.0
            }

        h, w = vehicle_crop.shape[:2]
        # Calculate heuristic crop quality based on resolution and variance
        resolution_score = min(1.0, (w * h) / (120.0 * 100.0))
        gray = cv2.cvtColor(vehicle_crop, cv2.COLOR_BGR2GRAY) if len(vehicle_crop.shape) == 3 else vehicle_crop
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        sharpness_score = min(1.0, lap_var / 150.0)
        quality = round(float(0.6 * resolution_score + 0.4 * sharpness_score), 3)

        try:
            # 1. Resize to ResNet standard 224x224
            resized = cv2.resize(vehicle_crop, (224, 224), interpolation=cv2.INTER_AREA)
            
            # 2. BGR to RGB and scale to [0, 1]
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            
            # 3. Standard ImageNet Normalization
            normalized = (rgb - self.mean) / self.std
            
            # 4. HWC -> CHW -> NCHW Tensor
            tensor = torch.from_numpy(normalized).permute(2, 0, 1).unsqueeze(0).to(self.device)

            # 5. Extract Feature Vector
            with torch.no_grad():
                features = self.model(tensor)
                vec = features.squeeze().cpu().numpy().astype(np.float32)

            # 6. Flatten and L2-Normalize
            norm = np.linalg.norm(vec)
            if norm > 1e-7:
                vec = vec / norm
            else:
                vec = np.zeros(512, dtype=np.float32)

            return {
                "embedding": vec.tolist(),
                "dimension": 512,
                "quality": quality
            }

        except Exception as e:
            logger.error(f"Error during feature extraction: {e}")
            return {
                "embedding": [0.0] * 512,
                "dimension": 512,
                "quality": 0.0
            }
