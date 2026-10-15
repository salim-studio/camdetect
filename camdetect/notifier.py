"""Notifications — webhook + Telegram with cooldown to prevent spam."""
import json
import threading
import time
import urllib.parse
import urllib.request


class Notifier:
    def __init__(self, cfg: dict):
        self.cfg = cfg.get("notify", {})
        self.cool = {}
        self.cooldown = cfg.get("alerts", {}).get("cooldown_sec", 20)
        self.lock = threading.Lock()

    def update(self, cfg: dict):
        self.cfg = cfg.get("notify", {})
        self.cooldown = cfg.get("alerts", {}).get("cooldown_sec", 20)

    def _allowed(self, key) -> bool:
        now = time.time()
        with self.lock:
            if now - self.cool.get(key, 0) < self.cooldown:
                return False
            self.cool[key] = now
            return True

    def send(self, title, body="", image=None, key="global"):
        if not self.cfg.get("enabled", True):
            return False
        if not self._allowed(key):
            return False
        threading.Thread(target=self._fanout, args=(title, body, image),
                         daemon=True).start()
        return True

    def _fanout(self, title, body, image):
        if self.cfg.get("webhook_url"):
            self._webhook(title, body)
        if self.cfg.get("telegram_bot") and self.cfg.get("telegram_chat"):
            self._telegram(f"{title}\n{body}")
        # Pushover via webhook supported: user sets https://api.pushover.net/1/messages.json

    def _webhook(self, title, body):
        try:
            data = json.dumps({"title": title, "body": body,
                               "ts": time.time()}).encode()
            req = urllib.request.Request(self.cfg["webhook_url"], data=data,
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=6).read()
        except Exception as e:
            print("[camdetect] webhook failed:", e)

    def _telegram(self, text):
        try:
            url = (f"https://api.telegram.org/bot{self.cfg['telegram_bot']}"
                   f"/sendMessage?chat_id={self.cfg['telegram_chat']}"
                   f"&text={urllib.parse.quote(text[:3500])}")
            urllib.request.urlopen(url, timeout=8).read()
        except Exception as e:
            print("[camdetect] telegram failed:", e)
