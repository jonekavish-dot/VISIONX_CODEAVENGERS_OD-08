"""
IVACS V-TRACE MP4 Video Source
Handles sequential frame ingestion from local MP4 video files.
"""

import os
import cv2
import numpy as np
from typing import Tuple, Optional
from backend.video.base_source import VideoSource

class MP4Source(VideoSource):
    """VideoSource implementation for MP4 files."""
    
    def __init__(self, file_path: str, camera_id: str = "CAM-01"):
        super().__init__(source_uri=file_path, camera_id=camera_id)
        self.cap: Optional[cv2.VideoCapture] = None
        self._fps = 30.0
        self._total_frames = 0
        self._current_frame_idx = 0

    def open(self) -> bool:
        is_url = self.source_uri.startswith(("http://", "https://", "rtsp://"))
        if not is_url and not os.path.exists(self.source_uri):
            self.is_opened = False
            return False
            
        self.cap = cv2.VideoCapture(self.source_uri)
        if not self.cap.isOpened():
            self.is_opened = False
            return False
            
        self.is_opened = True
        self._fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self._current_frame_idx = 0
        return True

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray], int]:
        if not self.is_opened or self.cap is None:
            return False, None, self._current_frame_idx

        ret, frame = self.cap.read()
        if not ret or frame is None:
            return False, None, self._current_frame_idx

        self._current_frame_idx += 1
        return True, frame, self._current_frame_idx

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.is_opened = False

    def get_fps(self) -> float:
        return self._fps

    def get_total_frames(self) -> int:
        return self._total_frames
