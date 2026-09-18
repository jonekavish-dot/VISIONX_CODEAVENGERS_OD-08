"""
IVACS V-TRACE: YouTube Live Stream Video Source
Extracts playable live media stream URLs using yt-dlp without downloading the entire video,
and feeds frames through the standard VideoSource interface into FrameProcessor.
"""

import logging
import cv2
import numpy as np
from typing import Tuple, Optional, Dict, Any
from backend.video.base_source import VideoSource

logger = logging.getLogger("vtrace.youtube_source")

# Stream unavailable constant
YOUTUBE_STREAM_UNAVAILABLE = "YOUTUBE_STREAM_UNAVAILABLE"


class YouTubeSource(VideoSource):
    """
    VideoSource implementation for public YouTube livestreams.
    Uses yt-dlp for direct HLS/MP4 live stream extraction and OpenCV VideoCapture for decoding.
    """

    def __init__(self, youtube_url: str, camera_id: str = "CAM-YOUTUBE-LIVE"):
        super().__init__(source_uri=youtube_url, camera_id=camera_id)
        self.stream_url: Optional[str] = None
        self.title: str = "Public YouTube Stream"
        self.is_live: bool = False
        self.last_error: Optional[str] = None
        self.cap: Optional[cv2.VideoCapture] = None
        self._fps: float = 30.0
        self._current_frame_idx: int = 0
        self._metadata: Dict[str, Any] = {}

    def extract_stream_url(self) -> Optional[str]:
        """
        Extract direct playable live stream URL via yt-dlp without downloading.
        Returns the stream URL or None on failure.
        """
        try:
            import yt_dlp
        except ImportError:
            logger.error("yt-dlp is not installed. Install via `pip install yt-dlp`.")
            self.last_error = YOUTUBE_STREAM_UNAVAILABLE
            return None

        # Practical format selection: prioritize lightweight 720p/480p streams for fast edge inference
        ydl_opts = {
            "format": "bestvideo[height<=720][ext=mp4]+bestaudio/best[height<=720]/best",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "extract_flat": False,
            "nocheckcertificate": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.source_uri, download=False)
                if not info:
                    self.last_error = YOUTUBE_STREAM_UNAVAILABLE
                    return None

                self.title = info.get("title", "Public YouTube Stream")
                self.is_live = bool(info.get("is_live", False))
                self.stream_url = info.get("url")

                # Fallback to direct formats if top-level url is missing
                if not self.stream_url and "formats" in info:
                    formats = info.get("formats", [])
                    # Pick best available format with a valid URL
                    for fmt in reversed(formats):
                        f_url = fmt.get("url")
                        if f_url:
                            self.stream_url = f_url
                            break

                self._metadata = {
                    "title": self.title,
                    "is_live": self.is_live,
                    "channel": info.get("uploader") or info.get("channel"),
                    "view_count": info.get("view_count"),
                    "resolution": f"{info.get('width', 'auto')}x{info.get('height', 'auto')}"
                }

                if not self.stream_url:
                    self.last_error = YOUTUBE_STREAM_UNAVAILABLE
                    return None

                self.last_error = None
                return self.stream_url

        except Exception as e:
            logger.warning(f"Failed to extract stream from YouTube URL '{self.source_uri}': {e}")
            self.last_error = YOUTUBE_STREAM_UNAVAILABLE
            return None

    def open(self) -> bool:
        """
        Extracts the live media URL and opens OpenCV VideoCapture.
        """
        if not self.source_uri:
            self.is_opened = False
            self.last_error = YOUTUBE_STREAM_UNAVAILABLE
            return False

        stream_url = self.extract_stream_url()
        if not stream_url:
            self.is_opened = False
            return False

        try:
            self.cap = cv2.VideoCapture(stream_url)
            if not self.cap.isOpened():
                logger.warning(f"OpenCV failed to open live stream: {stream_url}")
                self.is_opened = False
                self.last_error = YOUTUBE_STREAM_UNAVAILABLE
                return False

            self.is_opened = True
            fps_val = self.cap.get(cv2.CAP_PROP_FPS)
            self._fps = fps_val if fps_val and fps_val > 0 else 30.0
            self._current_frame_idx = 0
            self.last_error = None
            logger.info(f"Connected to YouTube livestream: '{self.title}' (FPS: {self._fps:.2f})")
            return True

        except Exception as e:
            logger.error(f"Error opening YouTube stream with OpenCV: {e}")
            self.is_opened = False
            self.last_error = YOUTUBE_STREAM_UNAVAILABLE
            return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray], int]:
        """
        Reads next frame from the live YouTube stream.
        """
        if not self.is_opened or self.cap is None:
            return False, None, self._current_frame_idx

        try:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                return False, None, self._current_frame_idx

            self._current_frame_idx += 1
            return True, frame, self._current_frame_idx

        except Exception as e:
            logger.warning(f"Error reading frame from YouTube stream: {e}")
            return False, None, self._current_frame_idx

    def close(self):
        """
        Releases video capture resources and resets state.
        """
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        self.is_opened = False
        logger.info(f"YouTubeSource closed for '{self.title}'")

    def get_fps(self) -> float:
        return self._fps

    def get_total_frames(self) -> int:
        return -1  # Unbounded live media stream

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "is_live": self.is_live,
            "stream_url": self.stream_url,
            "last_error": self.last_error,
            "fps": self._fps,
            "current_frame": self._current_frame_idx,
            "is_opened": self.is_opened,
            **self._metadata
        }
