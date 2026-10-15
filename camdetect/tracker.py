"""Lightweight centroid tracker (much faster than Kalman-based trackers) — enough for alerts and counting."""
import math


class Track:
    __slots__ = ("id", "cx", "cy", "cls", "label", "conf",
                 "disappeared", "age", "px", "py", "speed")
    def __init__(self, tid, cx, cy, cls, label, conf):
        self.id = tid
        self.cx, self.cy = cx, cy
        self.px, self.py = cx, cy
        self.cls, self.label, self.conf = cls, label, conf
        self.disappeared = 0
        self.age = 1
        self.speed = 0.0


class CentroidTracker:
    """Greedy Euclidean-distance matching. Small O(n*m) — runs at 500+ FPS."""
    def __init__(self, max_disappeared=25, max_distance=90):
        self.next_id = 1
        self.tracks: dict[int, Track] = {}
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def update(self, dets):
        """dets: list of dict(x1,y1,x2,y2,cls,label,conf) in pixel coordinates."""
        if not dets:
            dead = []
            for t in self.tracks.values():
                t.disappeared += 1
                if t.disappeared > self.max_disappeared:
                    dead.append(t.id)
            for tid in dead:
                del self.tracks[tid]
            return []
        centers = [((d["x1"] + d["x2"]) / 2, (d["y1"] + d["y2"]) / 2) for d in dets]
        tids = list(self.tracks.keys())
        used_d, used_t = set(), set()
        pairs = []
        for ti, tid in enumerate(tids):
            t = self.tracks[tid]
            for di, (cx, cy) in enumerate(centers):
                pairs.append((math.hypot(t.cx - cx, t.cy - cy), ti, di))
        pairs.sort(key=lambda p: p[0])
        match_d, match_t = {}, {}
        for dist, ti, di in pairs:
            if dist > self.max_distance or ti in match_t or di in match_d:
                continue
            match_t[ti] = di
            match_d[di] = ti
        out = []
        for ti, tid in enumerate(tids):
            t = self.tracks[tid]
            if ti in match_t:
                d = dets[match_t[ti]]
                cx, cy = centers[match_t[ti]]
                t.speed = math.hypot(cx - t.cx, cy - t.cy)
                t.px, t.py, t.cx, t.cy = t.cx, t.cy, cx, cy
                t.cls, t.label, t.conf = d["cls"], d["label"], d["conf"]
                t.disappeared = 0
                t.age += 1
                used_t.add(tid)
                used_d.add(match_t[ti])
                out.append(t)
            else:
                t.disappeared += 1
        for tid in [k for k, t in self.tracks.items() if t.disappeared > self.max_disappeared]:
            del self.tracks[tid]
        for di, d in enumerate(dets):
            if di in used_d:
                continue
            cx, cy = centers[di]
            t = Track(self.next_id, cx, cy, d["cls"], d["label"], d["conf"])
            self.tracks[self.next_id] = t
            out.append(t)
            self.next_id += 1
        return out
