"""
IVACS V-TRACE Webcam Video Source
Handles USB/Integrated camera inputs (e.g. index 0, 1).
"""

import cv2
import numpy as np
from typing import Tuple, Optional
from backend.video.base_source import VideoSource

class WebcamSource(VideoSource):
    """VideoSource implementation for local webcams."""
    
    def __init__(self, device_index: int = 0, camera_id: str = "CAM-01"):
        super().__init__(source_uri=str(device_index), camera_id=camera_id)
        self.device_index = int(device_index)
        self.cap: Optional[cv2.VideoCapture] = None
        self._fps = 30.0
        self._current_frame_idx = 0

    def open(self) -> bool:
        try:
            self.cap = cv2.VideoCapture(self.device_index)
            if not self.cap.isOpened():
                self.is_opened = False
                return False
            self.is_opened = True
            fps_val = self.cap.get(cv2.CAP_PROP_FPS)
            self._fps = fps_val if fps_val and fps_val > 0 else 30.0
            return True
        except Exception:
            self.is_opened = False
            return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray], int]:
        if not self.is_opened or self.cap is None:
            return False, None, self._current_frame_idx

        try:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                return False, None, self._current_frame_idx
            self._current_frame_idx += 1
            return True, frame, self._current_frame_idx
        except Exception:
            return False, None, self._current_frame_idx

    def close(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        self.is_opened = False

    def get_fps(self) -> float:
        return self._fps

    def get_total_frames(self) -> int:
        return -1
