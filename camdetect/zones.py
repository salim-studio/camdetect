"""Zones of interest (polygons) — include/exclude filtering, numpy-free."""
import cv2
import numpy as np


def point_in_poly(px, py, poly) -> bool:
    """Pure-Python ray casting — fast enough for small polygons."""
    inside = False
    n = len(poly)
    if n < 3:
        return True
    x1, y1 = poly[0]
    for i in range(1, n + 1):
        x2, y2 = poly[i % n]
        if ((y1 > py) != (y2 > py)) and (px < (x2 - x1) * (py - y1) / (y2 - y1 + 1e-9) + x1):
            inside = not inside
        x1, y1 = x2, y2
    return inside


def box_center_in_zone(box, poly, w=1.0, h=1.0, invert=False) -> bool:
    """box = [x1,y1,x2,y2] in normalized pixels (0..1)."""
    if not poly or len(poly) < 3:
        return True
    cx = (box[0] + box[2]) / 2
    cy = (box[1] + box[3]) / 2
    inside = point_in_poly(cx, cy, poly)
    return (not inside) if invert else inside


def draw_zones(frame, zones):
    """Draw translucent zones over the frame (BGR)."""
    if not zones:
        return frame
    ov = frame.copy()
    for z in zones:
        poly = z.get("poly") or []
        if len(poly) < 3:
            continue
        h, w = frame.shape[:2]
        pts = (np.array(poly, dtype=np.float32) * np.array([w, h])).astype(np.int32)
        color = (0, 200, 0) if z.get("mode", "include") == "include" else (0, 0, 255)
        cv2.fillPoly(ov, [pts], color)
        cv2.polylines(frame, [pts], True, color, 2)
    return cv2.addWeighted(ov, 0.18, frame, 0.82, 0)
