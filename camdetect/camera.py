"""Camera manager — one capture thread + one inference thread per camera.
The trick: a size-1 queue (latest frame only) + frame_skip + motion gate => always low latency.
"""
import cv2
import threading
import time
import queue
import numpy as np
from .detector import Detector, MotionGate
from .tracker import CentroidTracker
from .zones import box_center_in_zone, draw_zones


def draw_box(frame, x1, y1, x2, y2, label, tid, color=(0, 220, 0)):
    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
    txt = f"{label} #{tid}"
    (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    cv2.rectangle(frame, (int(x1), int(y1) - th - 8), (int(x1) + tw + 6, int(y1)), color, -1)
    cv2.putText(frame, txt, (int(x1) + 3, int(y1) - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)


class Camera:
    def __init__(self, name, src, cfg, store, notifier, on_event):
        self.name = name
        self.src = src
        self.cfg = cfg
        self.store = store
        self.notifier = notifier
        self.on_event = on_event
        self.zones = []
        self.running = False
        self.cap = None
        self.q = queue.Queue(maxsize=1)
        self.latest = None          # annotated BGR for MJPEG
        self.raw = None             # last raw frame (for zone editor snapshot)
        self.fps = 0.0
        self.det_ms = 0.0
        self.frames = 0
        self.dets = 0
        self.status = "init"
        inf = cfg.get("inference", {})
        self.det = Detector(inf.get("engine", "auto"), inf.get("imgsz", 480), inf.get("conf", 0.45))
        self.gate = MotionGate()
        tr = cfg.get("tracking", {})
        self.tracker = CentroidTracker(tr.get("max_disappeared", 25), tr.get("max_distance", 90))
        self.skip = max(1, int(inf.get("frame_skip", 2)))
        self._seen_tracks = set()

    # ---------- lifecycle ----------
    def start(self):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._capture_loop, daemon=True, name=f"cap-{self.name}").start()
        threading.Thread(target=self._infer_loop, daemon=True, name=f"inf-{self.name}").start()

    def stop(self):
        self.running = False
        try:
            if self.cap is not None:
                self.cap.release()
        except Exception:
            pass

    def _open(self):
        s = self.src
        try:
            idx = int(s)
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW) if hasattr(cv2, "CAP_DSHOW") else cv2.VideoCapture(idx)
        except (ValueError, TypeError):
            cap = cv2.VideoCapture(s)
        if cap is not None and cap.isOpened():
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return cap
        return None

    def _capture_loop(self):
        fails = 0
        while self.running:
            if self.cap is None:
                self.status = "connecting"
                self.cap = self._open()
                if self.cap is None:
                    time.sleep(2)
                    fails += 1
                    continue
                self.status = "live"
                fails = 0
            ok, frame = self.cap.read()
            if not ok or frame is None:
                fails += 1
                self.status = "reconnecting"
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
                time.sleep(1 if fails < 5 else 3)
                continue
            fails = 0
            self.raw = frame
            try:
                if self.q.full():
                    self.q.get_nowait()
                self.q.put_nowait(frame)
            except queue.Full:
                pass
        self.status = "stopped"

    def _infer_loop(self):
        n = 0
        t_prev = time.time()
        while self.running:
            try:
                frame = self.q.get(timeout=1.0)
            except queue.Empty:
                continue
            n += 1
            t_now = time.time()
            inst = 1.0 / max(1e-6, t_now - t_prev)
            t_prev = t_now
            self.fps = self.fps * 0.85 + inst * 0.15
            self.frames += 1
            inf = self.cfg.get("inference", {})
            # motion gate: skip heavy inference when nothing is moving
            dets = []
            do_infer = (n % self.skip == 0)
            motion = self.gate.amount(frame)
            if do_infer and inf.get("motion_gate", True) and motion < inf.get("motion_threshold", 1.2) and self.frames > 30:
                dets = []
                self.det.last_ms = 0
            elif do_infer:
                dets = self.det.detect(frame)
                self.det_ms = getattr(self.det, "last_ms", 0)
            # zone filter (normalized)
            h, w = frame.shape[:2]
            kept = []
            for d in dets:
                nb = [d["x1"] / w, d["y1"] / h, d["x2"] / w, d["y2"] / h]
                ok_zone = True if not self.zones else False
                for z in self.zones:
                    if box_center_in_zone(nb, z.get("poly", []), invert=(z.get("mode") == "exclude")):
                        if z.get("mode", "include") == "include":
                            ok_zone = True
                            break
                if not self.zones:
                    ok_zone = True
                if ok_zone:
                    kept.append(d)
            tracks = self.tracker.update(kept)
            # class allow-list
            allowed = set(self.cfg.get("alerts", {}).get("classes", []) or [])
            ann = draw_zones(frame.copy(), self.zones)
            for t in tracks:
                # find box
                b = None
                for d in kept:
                    cx = (d["x1"] + d["x2"]) / 2
                    cy = (d["y1"] + d["y2"]) / 2
                    if abs(cx - t.cx) < 4 and abs(cy - t.cy) < 4:
                        b = d
                        break
                x1 = t.cx - 40 if b is None else b["x1"]
                y1 = t.cy - 60 if b is None else b["y1"]
                x2 = t.cx + 40 if b is None else b["x2"]
                y2 = t.cy + 60 if b is None else b["y2"]
                if t.age >= 2:
                    draw_box(ann, x1, y1, x2, y2, t.label, t.id)
                # fire event once per new track (dedupes alerts)
                if t.age == 2 and (not allowed or t.label in allowed or str(t.cls) in allowed):
                    key = (t.id, t.label)
                    if key not in self._seen_tracks:
                        self._seen_tracks.add(key)
                        if len(self._seen_tracks) > 2000:
                            self._seen_tracks.clear()
                        try:
                            self.on_event(self, t, ann.copy())
                        except Exception as e:
                            print("[camdetect] on_event error:", e)
            cv2.putText(ann, f"{self.name} {self.fps:.0f}fps {self.det_ms:.0f}ms [{self.det.engine}]",
                        (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            self.latest = ann
            self.dets = len(tracks)


class Manager:
    def __init__(self, cfg, store, notifier, on_event):
        self.cfg = cfg
        self.store = store
        self.notifier = notifier
        self.on_event = on_event
        self.cams: dict[str, Camera] = {}
        self.lock = threading.Lock()

    def sync(self, cfg):
        self.cfg = cfg
        want = {c["name"]: c for c in cfg.get("cameras", [])}
        with self.lock:
            for name in list(self.cams):
                if name not in want:
                    self.cams[name].stop()
                    del self.cams[name]
            for name, c in want.items():
                if name in self.cams:
                    cam = self.cams[name]
                    if cam.src != c["src"]:
                        cam.stop()
                        del self.cams[name]
                    else:
                        cam.cfg = cfg
                        cam.zones = c.get("zones", [])
                        cam.skip = max(1, int(cfg.get("inference", {}).get("frame_skip", 2)))
                        cam.det.set_conf(cfg.get("inference", {}).get("conf", 0.45))
                        continue
                cam = Camera(name, c["src"], cfg, self.store, self.notifier, self.on_event)
                cam.zones = c.get("zones", [])
                cam.start()
                self.cams[name] = cam
