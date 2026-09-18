"""
IVACS V-TRACE Video Source Abstraction
Provides a uniform interface for MP4 files, RTSP streams, and Webcams.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional, Generator
import numpy as np

class VideoSource(ABC):
    """Abstract base class for all video sources."""
    
    def __init__(self, source_uri: str, camera_id: str = "CAM-01"):
        self.source_uri = source_uri
        self.camera_id = camera_id
        self.is_opened = False
        self.frame_count = 0
        
    @abstractmethod
    def open(self) -> bool:
        """Open the video stream or file. Returns True if successfully opened."""
        pass
        
    @abstractmethod
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray], int]:
        """
        Read the next frame.
        Returns:
            (success: bool, frame: Optional[np.ndarray], frame_number: int)
        """
        pass
        
    @abstractmethod
    def close(self):
        """Release video resources."""
        pass

    @abstractmethod
    def get_fps(self) -> float:
        """Return frames per second of the source, or default 30.0."""
        pass

    @abstractmethod
    def get_total_frames(self) -> int:
        """Return total frame count if known (e.g. for files), or -1 for live streams."""
        pass

    def stream_frames(self, sample_every_n: int = 1) -> Generator[Tuple[int, np.ndarray], None, None]:
        """
        Generator yielding (frame_number, frame) with sampling every N frames.
        Does not crash on corrupt frames or end of stream.
        """
        if not self.is_opened:
            if not self.open():
                return

        current_idx = 0
        sample_step = max(1, sample_every_n)
        
        try:
            while True:
                success, frame, frame_num = self.read_frame()
                if not success or frame is None:
                    break
                    
                current_idx += 1
                if current_idx % sample_step == 0:
                    yield (frame_num, frame)
        finally:
            self.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
