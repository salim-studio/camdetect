# camdetect

**Fast, lightweight AI surveillance for any camera — detection, tracking, alerts, and search.**

<img src="https://img.shields.io/badge/version-1.0.0-22c55e"> <img src="https://img.shields.io/badge/python-3.9%2B-3776AB"> <img src="https://img.shields.io/badge/license-MIT-ff69b4"> <img src="https://img.shields.io/badge/copyright-2026%20salim--slimani-blue">

camdetect turns any camera — webcam, RTSP/IP camera, video file, or stream URL — into a smart security camera with real-time object detection, persistent tracking, zone-based alerts, instant search, and mobile/web notifications. It runs efficiently on any machine: no GPU, no ffmpeg, no heavy frameworks.

---

## Highlights

- **Fast by design** — motion gating + frame skipping (3-5x faster than running inference on every frame); latest-frame queue means near-zero stream latency.
- **Three detection engines, automatic fallback** — YOLOv8n (accurate, optional) → HOG people detector (instant) → motion blobs (always works, even offline).
- **Lightweight tracker** — a centroid tracker with stable IDs, built for hundreds of frames per second.
- **Live web dashboard** — multi-camera MJPEG streaming with per-camera FPS, latency, engine, and status.
- **Zones** — draw include/exclude polygons directly on a camera snapshot.
- **Search & archive** — full-text, class, camera, and date search over stored events with thumbnails.
- **Notifications** — Webhooks (Discord / Slack / Home Assistant / n8n) and Telegram, with per-camera cooldown.
- **Self-hosted & private** — everything stays on your machine (SQLite storage, no cloud).
- **Clean storage** — automatic pruning of old events keeps disk usage under control.

## Quick start (2 minutes)

```bash
git clone https://github.com/salim-studio/camdetect.git
cd camdetect
pip install -r requirements.txt
python -m camdetect
```

Open **http://127.0.0.1:8080**

On Windows you can simply double-click `run.bat`.

For higher accuracy (optional):

```bash
pip install ultralytics "opencv-python<5"
```

YOLOv8n is then picked up automatically — no configuration needed. Without it, camdetect still works instantly using HOG/motion.

## Add a camera

From the web UI (**➕ Add camera**) or the API:

| Source | Example |
|---|---|
| Webcam | `0` or `1` |
| IP / RTSP camera | `rtsp://user:pass@192.168.1.10:554/stream` |
| Video file | `C:/videos/garage.mp4` |
| Stream URL | `https://example.com/stream.m3u8` |

## Features

| Feature | Description |
|---|---|
| 🔴 Live view | MJPEG stream per camera with live FPS / ms / engine badges |
| 🧠 Detection | person, car, dog, cat, … (YOLO) or people (HOG) or motion blobs |
| 🧭 Tracking | Stable track IDs, count of unique objects per event |
| 🗺️ Zones | Draw include/exclude regions on a live snapshot |
| 🔎 Search | Filter events by text, class, date, or camera + thumbnails |
| 🔔 Alerts | Webhook + Telegram with cooldown to prevent spam |
| ⚙️ Settings | Engine, image size, confidence, frame skip — live from the UI |
| 🌐 Languages | English interface |

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Server status & engines |
| GET | `/api/cameras` | List cameras |
| POST | `/api/cameras` | Add camera `{"name","src"}` |
| DELETE | `/api/cameras/<name>` | Remove camera |
| GET | `/stream/<name>` | MJPEG live stream |
| GET | `/snap/<name>` | JPEG snapshot (for zone drawing) |
| GET | `/api/events?q=&label=&date=&cam=&limit=` | Search events |
| GET | `/api/thumb/<id>` | Event thumbnail |
| POST | `/api/zones/<name>` | Save zone polygons |
| GET/POST | `/api/config` | Read / update settings |
| POST | `/api/notify_test` | Send a test notification |
| POST | `/api/prune` | Clean old events now |

## Configuration (`config.json`)

```json
{
  "server":    { "host": "127.0.0.1", "port": 8080 },
  "inference": { "engine": "auto", "imgsz": 480, "conf": 0.45,
                 "frame_skip": 2, "motion_gate": true, "motion_threshold": 1.2 },
  "tracking":  { "max_disappeared": 25, "max_distance": 90 },
  "alerts":    { "cooldown_sec": 20, "save_thumbs": true },
  "notify":    { "webhook_url": "", "telegram_bot": "", "telegram_chat": "" },
  "cameras":   []
}
```

- **engine**: `auto` | `yolo` | `hog` | `motion` — `auto` picks the best available.
- **imgsz**: smaller = faster (try `320` on weak hardware).
- **frame_skip**: run detection every N frames.
- **motion_gate**: skip inference entirely when the scene is static.

## Project layout

```
camdetect/
├── camdetect/
│   ├── app.py        # Flask server: API, MJPEG, UI
│   ├── camera.py     # Capture + inference threads per camera
│   ├── detector.py   # YOLO / HOG / motion engines + motion gate
│   ├── tracker.py    # Lightweight centroid tracker
│   ├── storage.py    # SQLite (WAL) events + thumbnails + search
│   ├── notifier.py   # Webhook / Telegram with cooldown
│   ├── zones.py      # Polygon zone filtering + rendering
│   ├── config.py     # Config load/save with safe defaults
│   └── templates/    # Web dashboard
├── config.json
├── requirements.txt
├── run.bat
└── README.md
```

## Requirements

- Python 3.9+
- `opencv-python`, `numpy`, `Flask` (see `requirements.txt`)
- Optional: `ultralytics` (YOLOv8n)
- No GPU, no ffmpeg, no cloud account

## Performance tips

- Low FPS? Lower `imgsz` to `320` and raise `frame_skip` to `3`.
- Too many alerts? Increase `alerts.cooldown_sec` or use zones.
- RTSP unstable? camdetect auto-reconnects; give it 2-3 seconds.

## License

MIT © 2026 **salim-slimani**
