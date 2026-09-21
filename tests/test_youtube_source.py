"""
Unit tests for YouTubeSource and YouTube live streaming API.
All tests use mocked yt-dlp and OpenCV outputs so that automated tests do not require internet access.
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.video.youtube_source import YouTubeSource, YOUTUBE_STREAM_UNAVAILABLE
from backend.video.youtube_manager import YouTubeStreamManager
from backend.app import app


# 1. Test YouTubeSource successful extraction and frame reading
def test_youtube_source_success():
    mock_info = {
        "title": "Mock Live Traffic Camera",
        "is_live": True,
        "url": "https://manifest.googlevideo.com/api/manifest/hls_playlist/mock.m3u8",
        "uploader": "Traffic Live 24/7",
        "width": 1280,
        "height": 720
    }

    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    with patch("yt_dlp.YoutubeDL") as MockYDL:
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        MockYDL.return_value.__enter__.return_value = mock_ydl_instance

        with patch("cv2.VideoCapture") as MockCap:
            mock_cap_instance = MagicMock()
            mock_cap_instance.isOpened.return_value = True
            mock_cap_instance.get.return_value = 30.0
            mock_cap_instance.read.return_value = (True, dummy_frame)
            MockCap.return_value = mock_cap_instance

            source = YouTubeSource("https://www.youtube.com/watch?v=mock_video_id")
            
            # Test open
            opened = source.open()
            assert opened is True
            assert source.is_opened is True
            assert source.title == "Mock Live Traffic Camera"
            assert source.is_live is True
            assert source.get_fps() == 30.0
            assert source.get_total_frames() == -1

            # Test read_frame
            success, frame, idx = source.read_frame()
            assert success is True
            assert frame is not None
            assert idx == 1

            # Test metadata
            meta = source.get_metadata()
            assert meta["title"] == "Mock Live Traffic Camera"
            assert meta["is_live"] is True

            # Test close
            source.close()
            assert source.is_opened is False


# 2. Test YouTubeSource extraction failure yields YOUTUBE_STREAM_UNAVAILABLE
def test_youtube_source_extraction_failure():
    with patch("yt_dlp.YoutubeDL") as MockYDL:
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.side_effect = Exception("Video unavailable or private")
        MockYDL.return_value.__enter__.return_value = mock_ydl_instance

        source = YouTubeSource("https://www.youtube.com/watch?v=invalid_id")
        opened = source.open()
        assert opened is False
        assert source.is_opened is False
        assert YOUTUBE_STREAM_UNAVAILABLE in source.last_error


# 3. Test OpenCV connection failure yields YOUTUBE_STREAM_UNAVAILABLE
def test_youtube_source_opencv_failure():
    mock_info = {
        "title": "Mock Traffic Camera",
        "url": "https://manifest.googlevideo.com/mock.m3u8"
    }

    with patch("yt_dlp.YoutubeDL") as MockYDL:
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        MockYDL.return_value.__enter__.return_value = mock_ydl_instance

        with patch("cv2.VideoCapture") as MockCap:
            mock_cap_instance = MagicMock()
            mock_cap_instance.isOpened.return_value = False
            MockCap.return_value = mock_cap_instance

            source = YouTubeSource("https://www.youtube.com/watch?v=mock_video_id")
            opened = source.open()
            assert opened is False
            assert source.last_error == YOUTUBE_STREAM_UNAVAILABLE


# 4. Test YouTubeStreamManager status and state machine
def test_youtube_stream_manager_state():
    mgr = YouTubeStreamManager()
    status = mgr.get_status()
    assert status["status"] == "OFFLINE"
    assert status["stream_type"] == "PUBLIC_INTERNET_STREAM"
    assert "PUBLIC INTERNET STREAM" in status["label"]

    stopped = mgr.stop()
    assert stopped["status"] == "OFFLINE"


# 5. Test REST API Endpoints for YouTube Livestream
def test_youtube_api_endpoints():
    client = TestClient(app)

    # 1. Status endpoint
    res = client.get("/api/live/youtube/status")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert data["stream_type"] == "PUBLIC_INTERNET_STREAM"

    # 2. Latest frame endpoint (returns placeholder when offline)
    res_frame = client.get("/api/live/youtube/frame")
    assert res_frame.status_code == 200
    assert res_frame.headers["content-type"] == "image/jpeg"
    assert len(res_frame.content) > 0

    # 3. Latest detection endpoint
    res_latest = client.get("/api/live/youtube/latest")
    assert res_latest.status_code == 200
    latest_data = res_latest.json()
    assert "status" in latest_data
    assert "label" in latest_data

    # 4. Stop endpoint
    res_stop = client.post("/api/live/youtube/stop")
    assert res_stop.status_code == 200
    assert res_stop.json()["status"] == "OFFLINE"

    # 5. Start endpoint validation (empty URL returns 400)
    res_empty = client.post("/api/live/youtube/start", json={"url": "   "})
    assert res_empty.status_code == 400
