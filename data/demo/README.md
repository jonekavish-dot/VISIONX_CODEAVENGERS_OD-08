# IVACS V-TRACE: Demo Video Directory

Place your CCTV construction site test video files in this directory.

### Default Video File:
`data/demo/construction_site.mp4`

### Supported Video Formats:
* `.mp4` (H.264 / MPEG-4 / AVC1)
* `.avi`, `.mov`, `.mkv`

### Generating Demo Video:
To generate or re-generate a synthetic construction site CCTV video with vehicles and license plates:
```bash
python create_demo_video.py
```

### Frame Sampling:
You can adjust the sampling rate in `backend/config.py` via `PROCESS_EVERY_N_FRAMES` (default: 3 frames) to optimize throughput for your CPU/GPU hardware.
