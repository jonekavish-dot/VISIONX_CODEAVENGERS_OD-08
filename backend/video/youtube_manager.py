"""
IVACS V-TRACE: YouTube Live Stream Background Manager
Manages the background ingestion, frame decimation, FrameProcessor execution,
alert evaluation, and JPEG frame streaming for public YouTube streams.
"""

import time
import logging
import threading
import cv2
import numpy as np
from typing import Optional, Dict, Any

from backend.video.youtube_source import YouTubeSource, YOUTUBE_STREAM_UNAVAILABLE
from backend.schemas.detection import ProcessingStatus

logger = logging.getLogger("vtrace.youtube_manager")


class YouTubeStreamManager:
    """
    Singleton-style manager for public YouTube live stream ingestion.
    Runs a non-blocking background thread processing live internet video frames
    through the existing native CV + OCR + Identity pipeline.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.status: str = "OFFLINE"  # OFFLINE, CONNECTING, CONNECTED, RECONNECTING, YOUTUBE_STREAM_UNAVAILABLE
        self.url: Optional[str] = None
        self.title: str = "Public YouTube Stream"
        self.is_live: bool = False
        self.fps: float = 0.0
        self.current_frame: int = 0
        self.processed_count: int = 0
        self.detections_count: int = 0
        self.last_error: Optional[str] = None
        self.latest_event: Optional[Dict[str, Any]] = None
        self.latest_annotated_jpeg: Optional[bytes] = None

        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._source: Optional[YouTubeSource] = None
        self._frame_processor = None
        self._alert_service = None

    def start(self, url: str, frame_processor, alert_service=None, process_every_n: int = 8) -> Dict[str, Any]:
        """
        Start ingesting and processing the specified public YouTube livestream.
        """
        with self.lock:
            if self.status in ("CONNECTING", "CONNECTED", "RECONNECTING") and self._worker_thread and self._worker_thread.is_alive():
                # Stop existing stream first
                self._stop_internal()

            self.status = "CONNECTING"
            self.url = url
            self.title = "Connecting to YouTube stream..."
            self.last_error = None
            self.processed_count = 0
            self.detections_count = 0
            self.latest_event = None
            self.latest_annotated_jpeg = None
            self._stop_event.clear()
            self._frame_processor = frame_processor
            self._alert_service = alert_service

            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                args=(url, process_every_n),
                daemon=True,
                name="YouTubeLiveIngestionWorker"
            )
            self._worker_thread.start()

            return {
                "status": self.status,
                "url": self.url,
                "message": "Connecting to live YouTube camera stream..."
            }

    def _worker_loop(self, url: str, process_every_n: int = 8):
        logger.info(f"Starting YouTube stream ingestion for: {url}")
        source = YouTubeSource(youtube_url=url, camera_id="CAM-PUBLIC-INTERNET")
        self._source = source

        opened = source.open()
        if not opened:
            with self.lock:
                self.status = YOUTUBE_STREAM_UNAVAILABLE
                self.last_error = source.last_error or YOUTUBE_STREAM_UNAVAILABLE
                logger.warning(f"YouTube stream unavailable for URL '{url}': {self.last_error}")
            return

        with self.lock:
            self.status = "CONNECTED"
            self.title = source.title
            self.is_live = source.is_live
            self.fps = source.get_fps()
            logger.info(f"YouTube stream connected: '{self.title}' (Live: {self.is_live}, FPS: {self.fps:.2f})")

        consecutive_read_failures = 0
        frame_idx = 0
        start_time = time.time()

        try:
            while not self._stop_event.is_set():
                success, frame, f_num = source.read_frame()

                if not success or frame is None:
                    consecutive_read_failures += 1
                    if consecutive_read_failures == 1:
                        with self.lock:
                            self.status = "RECONNECTING"
                            logger.warning("Temporary frame drop on YouTube stream, attempting to refresh HLS token...")

                    if consecutive_read_failures in (4, 8):
                        logger.info("Refreshing YouTube HLS stream URL via yt-dlp...")
                        source.open()

                    if consecutive_read_failures > 15:
                        with self.lock:
                            self.status = "OFFLINE"
                            self.last_error = "Stream disconnected after repeated read failures"
                            logger.warning(self.last_error)
                        break

                    time.sleep(0.5)
                    continue

                consecutive_read_failures = 0
                frame_idx += 1

                with self.lock:
                    if self.status == "RECONNECTING":
                        self.status = "CONNECTED"

                # Process every Nth frame to avoid lag and CPU/memory exhaustion on Render free tier
                if frame_idx % process_every_n != 0:
                    time.sleep(0.01)
                    continue

                if self._frame_processor is None:
                    continue

                try:
                    # Normalize frame size to max 960px width to save RAM on Render Free Tier (<512MB)
                    h, w = frame.shape[:2]
                    if w > 960:
                        target_h = int(h * (960.0 / w))
                        frame = cv2.resize(frame, (960, target_h), interpolation=cv2.INTER_AREA)

                    # Run native FrameProcessor pipeline (YOLOv8 + OpenCV + EasyOCR + ResNet18)
                    events, annotated_frame = self._frame_processor.process_frame(
                        frame=frame,
                        frame_number=f_num,
                        camera_id="CAM-PUBLIC-INTERNET",
                        save_evidence=True
                    )

                    # Encode annotated frame as JPEG for GET /api/live/youtube/frame
                    encode_success, jpeg_buf = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    jpeg_bytes = jpeg_buf.tobytes() if encode_success else None

                    # Count real vehicle detections
                    valid_detections = [e for e in events if e.status != ProcessingStatus.NO_VEHICLE and e.status != ProcessingStatus.ERROR]

                    with self.lock:
                        self.current_frame = f_num
                        self.processed_count += 1
                        self.detections_count += len(valid_detections)
                        if jpeg_bytes:
                            self.latest_annotated_jpeg = jpeg_bytes

                        if valid_detections:
                            self.latest_event = valid_detections[-1].model_dump()

                        # Update live calculated FPS
                        elapsed = max(0.001, time.time() - start_time)
                        self.fps = round(self.processed_count / elapsed, 1)

                    # Periodically invoke garbage collector to keep memory below 280MB cap
                    if self.processed_count % 4 == 0:
                        import gc
                        gc.collect()

                    time.sleep(0.03)

                except Exception as proc_err:
                    logger.error(f"Error processing frame {f_num} from YouTube stream: {proc_err}")

        except Exception as e:
            logger.error(f"Unexpected error in YouTube stream worker: {e}", exc_info=True)

            with self.lock:
                self.status = "OFFLINE"
                self.last_error = str(e)
        finally:
            source.close()
            with self.lock:
                if self.status not in (YOUTUBE_STREAM_UNAVAILABLE,):
                    self.status = "OFFLINE"
            logger.info("YouTube stream worker terminated cleanly.")

    def _stop_internal(self):
        """Internal stop without lock recursion."""
        self._stop_event.set()
        if self._source:
            self._source.close()
            self._source = None
        self.status = "OFFLINE"

    def stop(self) -> Dict[str, Any]:
        """
        Stop the active YouTube livestream ingestion gracefully.
        """
        with self.lock:
            self._stop_internal()
            return {
                "status": "OFFLINE",
                "message": "YouTube live stream stopped."
            }

    def get_status(self) -> Dict[str, Any]:
        """
        Returns full live status telemetry.
        """
        with self.lock:
            return {
                "status": self.status,
                "url": self.url,
                "title": self.title,
                "is_live": self.is_live,
                "fps": self.fps,
                "current_frame": self.current_frame,
                "processed_count": self.processed_count,
                "detections_count": self.detections_count,
                "last_error": self.last_error,
                "stream_type": "PUBLIC_INTERNET_STREAM",
                "label": "PUBLIC INTERNET STREAM (Not Construction Site CCTV)"
            }

    def get_latest_frame_jpeg(self) -> Optional[bytes]:
        """
        Returns latest JPEG bytes of the processed annotated frame.
        """
        with self.lock:
            return self.latest_annotated_jpeg

    def get_latest_event(self) -> Optional[Dict[str, Any]]:
        """
        Returns latest detection event dictionary.
        """
        with self.lock:
            return self.latest_event


# Shared global instance
youtube_stream_manager = YouTubeStreamManager()
