"""camdetect — fast, practical object detection, tracking and alerts for any camera. No ffmpeg required."""
from .config import load_config, save_config

__version__ = "1.0.0"
__all__ = ["load_config", "save_config"]
