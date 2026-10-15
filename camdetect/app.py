"""camdetect web server — lightweight Flask: MJPEG streaming + API + dashboard."""
import cv2
import time
from pathlib import Path
from flask import Flask, jsonify, request, Response, render_template, send_file

from .config import load_config, save_config, DEFAULT_PATH
from .storage import Store
from .notifier import Notifier
from .camera import Manager

BASE = Path(__file__).resolve().parent.parent
app = Flask(__name__, template_folder=str(BASE / "camdetect" / "templates"))

cfg = load_config()
store = Store()
notifier = Notifier(cfg)


def handle_event(cam, track, annotated):
    ts = time.time()
    eid = store.add(cam.name, ts, track.cls, track.label, track.conf, track.id)
    thumb = None
    try:
        if cfg.get("alerts", {}).get("save_thumbs", True):
            p = store.thumb_path(cam.name, eid)
            small = annotated
            if max(small.shape[:2]) > 640:
                h, w = small.shape[:2]
                s = 640 / max(h, w)
                small = cv2.resize(small, (int(w * s), int(h * s)))
            cv2.imwrite(str(p), small, [cv2.IMWRITE_JPEG_QUALITY, 82])
            thumb = str(p)
            import sqlite3
            with store.lock, store._con() as c:
                c.execute("UPDATE events SET thumb=? WHERE id=?", (thumb, eid))
    except Exception as e:
        print("[camdetect] thumb error:", e)
    notifier.send(f"🚨 {track.label} — {cam.name}",
                  f"confidence {track.conf:.2f} | {time.strftime('%H:%M:%S')}",
                  key=f"{cam.name}:{track.label}")


manager = Manager(cfg, store, notifier, handle_event)
manager.sync(cfg)


# ---------- pages ----------
@app.get("/")
def index():
    return render_template("index.html")


# ---------- APIs ----------
@app.get("/api/health")
def health():
    return jsonify({"ok": True, "engine": _engines(), "events": store.counts()["total"]})


def _engines():
    return {name: {"fps": round(c.fps, 1), "det_ms": round(c.det_ms, 1),
                   "engine": c.det.engine, "status": c.status, "src": str(c.src),
                   "tracks": c.dets} for name, c in manager.cams.items()}


@app.get("/api/cameras")
def list_cams():
    return jsonify([{"name": c["name"], "src": c["src"], "zones": c.get("zones", [])}
                    for c in cfg.get("cameras", [])])


@app.post("/api/cameras")
def add_cam():
    d = request.get_json(force=True)
    name, src = (d.get("name") or "").strip(), str(d.get("src") or "").strip()
    if not name or not src:
        return jsonify({"error": "name & src required"}), 400
    if any(c["name"] == name for c in cfg["cameras"]):
        return jsonify({"error": "name exists"}), 400
    cfg["cameras"].append({"name": name, "src": src, "zones": []})
    save_config(cfg)
    manager.sync(cfg)
    return jsonify({"ok": True})


@app.delete("/api/cameras/<name>")
def del_cam(name):
    cfg["cameras"] = [c for c in cfg["cameras"] if c["name"] != name]
    save_config(cfg)
    manager.sync(cfg)
    return jsonify({"ok": True})


@app.get("/api/stats")
def stats():
    return jsonify({"live": _engines(), "counts": store.counts()})


@app.get("/api/events")
def events():
    rows = store.search(cam=request.args.get("cam") or None,
                        label=request.args.get("label") or None,
                        date=request.args.get("date") or None,
                        q=request.args.get("q") or None,
                        limit=min(500, int(request.args.get("limit", 100))),
                        offset=int(request.args.get("offset", 0)))
    for r in rows:
        r["thumb_url"] = f"/api/thumb/{r['id']}" if r.get("thumb") else None
        r["time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ts"]))
    return jsonify(rows)


@app.get("/api/thumb/<int:eid>")
def thumb(eid):
    # direct lookup
    import sqlite3
    with store.lock, store._con() as c:
        row = c.execute("SELECT thumb FROM events WHERE id=?", (eid,)).fetchone()
    if not row or not row[0]:
        return jsonify({"error": "no thumb"}), 404
    p = Path(row[0])
    if not p.exists():
        return jsonify({"error": "missing"}), 404
    return send_file(p, mimetype="image/jpeg")


@app.post("/api/zones/<name>")
def zones(name):
    d = request.get_json(force=True)
    for c in cfg["cameras"]:
        if c["name"] == name:
            c["zones"] = d.get("zones", [])
            save_config(cfg)
            manager.sync(cfg)
            return jsonify({"ok": True})
    return jsonify({"error": "no cam"}), 404


@app.get("/api/config")
def get_cfg():
    safe = dict(cfg)
    return jsonify(safe)


@app.post("/api/config")
def set_cfg():
    d = request.get_json(force=True)
    for k in ("inference", "tracking", "alerts", "notify", "server"):
        if k in d:
            cfg[k].update(d[k]) if isinstance(d[k], dict) else None
    save_config(cfg)
    notifier.update(cfg)
    manager.sync(cfg)
    return jsonify({"ok": True})


@app.post("/api/notify_test")
def notify_test():
    ok = notifier.send("✅ camdetect is running", "This is a test message", key="test-now")
    return jsonify({"queued": ok})


@app.post("/api/prune")
def prune():
    store.prune()
    return jsonify({"ok": True})


# ---------- streaming ----------
def _mjpeg(cam_name):
    while True:
        cam = manager.cams.get(cam_name)
        if cam is None or cam.latest is None:
            blank = np_blank()
            ok, buf = cv2.imencode(".jpg", blank)
            chunk = buf.tobytes() if ok else b""
        else:
            ok, buf = cv2.imencode(".jpg", cam.latest, [cv2.IMWRITE_JPEG_QUALITY, 80])
            chunk = buf.tobytes() if ok else b""
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + chunk + b"\r\n")
        time.sleep(0.06)


def np_blank():
    import numpy as np
    img = np.zeros((360, 640, 3), np.uint8)
    cv2.putText(img, "connecting...", (220, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    return img


@app.get("/stream/<name>")
def stream(name):
    return Response(_mjpeg(name), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.get("/snap/<name>")
def snap(name):
    cam = manager.cams.get(name)
    if cam is None or cam.latest is None:
        img = np_blank()
    else:
        img = cam.latest
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return Response(buf.tobytes(), mimetype="image/jpeg")


def main():
    s = cfg.get("server", {})
    print(f"[camdetect] open http://{s.get('host', '127.0.0.1')}:{s.get('port', 8080)}")
    app.run(host=s.get("host", "127.0.0.1"), port=int(s.get("port", 8080)),
            threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
