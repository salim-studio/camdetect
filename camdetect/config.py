"""camdetect config — JSON load/save with safe defaults."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DEFAULT_PATH = BASE / "config.json"

DEFAULTS = {
    "server": {"host": "127.0.0.1", "port": 8080},
    "inference": {"engine": "auto", "imgsz": 480, "conf": 0.45,
                  "frame_skip": 2, "motion_gate": True, "motion_threshold": 1.2},
    "tracking": {"max_disappeared": 25, "max_distance": 90, "min_speed": 0.0},
    "alerts": {"cooldown_sec": 20, "save_thumbs": True, "save_clips": False, "classes": []},
    "notify": {"webhook_url": "", "telegram_bot": "", "telegram_chat": "", "enabled": True},
    "cameras": [],
}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path=None) -> dict:
    p = Path(path) if path else DEFAULT_PATH
    if p.exists():
        try:
            return _merge(DEFAULTS, json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            return json.loads(json.dumps(DEFAULTS))
    return json.loads(json.dumps(DEFAULTS))


def save_config(cfg: dict, path=None) -> None:
    p = Path(path) if path else DEFAULT_PATH
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
