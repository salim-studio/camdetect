"""camdetect — كشف وتتبع وتنبيه لأي كاميرا. سريع، عملي، بدون ffmpeg."""
from .config import load_config, save_config

__version__ = "1.0.0"
__all__ = ["load_config", "save_config"]
