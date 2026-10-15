"""Fast detection — 3 engines ordered by speed/accuracy:
yolo (optional, accurate) -> hog (people, no downloads) -> motion (always works).
+ a motion gate that skips heavy inference on static frames (3-5x faster).
"""
import cv2
import numpy as np
import time

COCO80 = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
          "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
          "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
          "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
          "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
          "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
          "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
          "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
          "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
          "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
          "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
          "toothbrush"]


class MotionGate:
    """Detects % of moving pixels — very cheap (grayscale + blur + diff)."""
    def __init__(self):
        self.prev = None

    def amount(self, frame) -> float:
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        g = cv2.GaussianBlur(g, (9, 9), 0)
        g = cv2.resize(g, (160, 90))
        if self.prev is None:
            self.prev = g
            return 100.0
        d = cv2.absdiff(self.prev, g)
        self.prev = g
        return float((d > 25).mean() * 100)


class Detector:
    def __init__(self, engine="auto", imgsz=480, conf=0.45):
        self.want = engine
        self.imgsz = imgsz
        self.conf = conf
        self.engine = "motion"
        self.yolo = None
        self.hog = None
        self._init_engine(engine)

    def _init_engine(self, engine):
        if engine in ("auto", "yolo"):
            try:
                from ultralytics import YOLO  # type: ignore
                self.yolo = YOLO("yolov8n.pt")  # auto-download on first run
                self.engine = "yolo"
                return
            except Exception as e:
                print(f"[camdetect] YOLO unavailable ({e}) -> fallback")
        if engine in ("auto", "hog", "motion"):
            try:
                if not hasattr(cv2, "HOGDescriptor"):
                    raise RuntimeError("HOG not in opencv build (needs opencv<5 or contrib)")
                hog = cv2.HOGDescriptor()
                hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
                self.hog = hog
                self.engine = "hog"
            except Exception as e:
                print(f"[camdetect] HOG unavailable ({e}) -> motion mode")
                self.engine = "motion"

    def set_conf(self, v: float):
        self.conf = float(v)

    def detect(self, frame):
        """-> list[{x1,y1,x2,y2,cls,label,conf}] in original frame pixel coordinates."""
        t0 = time.time()
        h, w = frame.shape[:2]
        scale = min(1.0, self.imgsz / max(h, w))
        small = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale < 1 else frame
        out = []
        if self.engine == "yolo" and self.yolo is not None:
            try:
                r = self.yolo.predict(small, conf=self.conf, verbose=False)[0]
                if r.boxes is not None:
                    for b, c, p in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
                        ci = int(c)
                        out.append({"x1": b[0] / scale, "y1": b[1] / scale,
                                    "x2": b[2] / scale, "y2": b[3] / scale,
                                    "cls": ci, "label": COCO80[ci] if ci < len(COCO80) else str(ci),
                                    "conf": float(p)})
            except Exception as e:
                print("[camdetect] yolo error, fallback hog:", e)
                self.engine = "hog" if self.hog is not None else "motion"
        if self.engine == "hog" and self.hog is not None:
            try:
                rects, weights = self.hog.detectMultiScale(small, winStride=(8, 8), padding=(8, 8), scale=1.05)
                for (x, y, ww, hh), wt in zip(rects, weights):
                    if float(wt) < 0.4:
                        continue
                    out.append({"x1": x / scale, "y1": y / scale, "x2": (x + ww) / scale,
                                "y2": (y + hh) / scale, "cls": 0, "label": "person",
                                "conf": float(min(0.99, 0.5 + float(wt) / 4))})
            except Exception:
                pass
        # motion fallback boxes (moving blobs) — only if nothing else found
        if not out and self.engine == "motion":
            out = self._motion_boxes(frame)
        self.last_ms = (time.time() - t0) * 1000
        return out

    def _motion_boxes(self, frame):
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        g = cv2.GaussianBlur(g, (21, 21), 0)
        if not hasattr(self, "_bg"):
            self._bg = g
            return []
        d = cv2.absdiff(self._bg, g)
        _, th = cv2.threshold(d, 30, 255, cv2.THRESH_BINARY)
        th = cv2.dilate(th, None, iterations=2)
        cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self._bg = cv2.addWeighted(self._bg, 0.95, g, 0.05, 0)
        boxes = []
        area_min = frame.shape[0] * frame.shape[1] * 0.005
        for c in cnts:
            if cv2.contourArea(c) < area_min:
                continue
            x, y, w, h = cv2.boundingRect(c)
            boxes.append({"x1": float(x), "y1": float(y), "x2": float(x + w),
                          "y2": float(y + h), "cls": -1, "label": "motion", "conf": 0.5})
        return boxes[:20]
