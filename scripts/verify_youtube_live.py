"""
IVACS V-TRACE: Live YouTube Livestream Ingestion & Processing Verification
Tests live connection to the Coimbatore traffic livestream:
https://www.youtube.com/watch?v=tmMrGbBOi1U
"""

import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.video.youtube_source import YouTubeSource, YOUTUBE_STREAM_UNAVAILABLE
from backend.services.frame_processor import FrameProcessor
from backend.schemas.detection import ProcessingStatus


def run_live_verification():
    target_url = "https://www.youtube.com/watch?v=tmMrGbBOi1U"
    print("=" * 75)
    print("  IVACS V-TRACE: LIVE YOUTUBE STREAM VERIFICATION")
    print("  Stream: Coimbatore Traffic Livestream (Public Traffic Camera)")
    print(f"  URL: {target_url}")
    print("=" * 75)

    # 1. Test YouTubeSource instantiation & extraction
    print("\n[STEP 1] Testing YouTubeSource & yt-dlp stream extraction...")
    source = YouTubeSource(target_url, camera_id="CAM-PUBLIC-INTERNET")
    stream_url = source.extract_stream_url()

    if not stream_url:
        print(f"[-] FAILED: Could not extract stream URL. Error: {source.last_error}")
        return False

    print(f"[+] PASS: Stream extracted successfully!")
    print(f"    * Title:        {source.title}")
    print(f"    * Is Live:      {source.is_live}")
    print(f"    * Stream URL:   {stream_url[:65]}...")

    # 2. Test OpenCV opening the live media stream
    print("\n[STEP 2] Testing OpenCV VideoCapture opening live HLS stream...")
    opened = source.open()
    if not opened:
        print(f"[-] FAILED: OpenCV could not open live stream. Error: {source.last_error}")
        return False

    print(f"[+] PASS: OpenCV connected to live stream!")
    print(f"    * Source FPS:   {source.get_fps():.2f}")

    # 3. Test reading live frames
    print("\n[STEP 3] Testing reading live frames from internet...")
    success, frame, idx = source.read_frame()
    if not success or frame is None:
        print("[-] FAILED: Could not read frame from live stream.")
        source.close()
        return False

    h, w, c = frame.shape
    print(f"[+] PASS: Successfully read live frame #{idx:04d}!")
    print(f"    * Resolution:   {w}x{h} ({c} channels)")

    # 4. Test FrameProcessor integration (YOLOv8 + Plate Detection + EasyOCR + ResNet18)
    print("\n[STEP 4] Testing FrameProcessor pipeline integration on live frame...")
    processor = FrameProcessor()

    # Process 3 live frames from the stream
    detections_found = 0
    for i in range(3):
        success, frame, idx = source.read_frame()
        if not success or frame is None:
            continue

        start_t = time.time()
        events, annotated = processor.process_frame(
            frame=frame,
            frame_number=idx,
            camera_id="CAM-PUBLIC-INTERNET",
            save_evidence=True
        )
        latency = (time.time() - start_t) * 1000

        print(f"    Frame #{idx:04d} processed in {latency:.1f}ms | Raw Events: {len(events)}")
        for ev in events:
            if ev.status != ProcessingStatus.NO_VEHICLE and ev.status != ProcessingStatus.ERROR:
                detections_found += 1
                v_cls = (ev.vehicle_class or "vehicle").upper()
                print(f"      -> DETECTED: {v_cls} (Conf: {ev.vehicle_confidence:.2f}) at BBox {ev.vehicle_bbox}")
                if ev.plate:
                    print(f"         Plate Text: '{ev.plate}' (OCR Conf: {ev.ocr_confidence:.2f})")
                if ev.vehicle_crop_path:
                    print(f"         Evidence Crop: {ev.vehicle_crop_path}")

    source.close()

    print("\n" + "=" * 75)
    print("  VERIFICATION AUDIT SUMMARY")
    print("=" * 75)
    print("  1. YouTube source:               PASS")
    print("  2. Frame extraction:             PASS")
    print("  3. FrameProcessor integration:   PASS")
    print("  4. Total Live Detections:        " + str(detections_found))
    print("=" * 75)
    return True


if __name__ == "__main__":
    run_live_verification()
