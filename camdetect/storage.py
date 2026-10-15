"""Storage — SQLite (WAL) + thumbnails. Fast search by class/camera/date/text."""
import sqlite3
import threading
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
DB = DATA / "camdetect.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS events(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 cam TEXT NOT NULL, ts REAL NOT NULL, date TEXT NOT NULL,
 cls INTEGER, label TEXT, conf REAL, track_id INTEGER,
 thumb TEXT, note TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_events_cam_ts ON events(cam, ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_label ON events(label);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
"""


class Store:
    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self._init()

    def _con(self):
        c = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=10)
        c.execute("PRAGMA journal_mode=WAL;")
        c.execute("PRAGMA synchronous=NORMAL;")
        return c

    def _init(self):
        with self.lock, self._con() as c:
            c.executescript(SCHEMA)

    def add(self, cam, ts, cls, label, conf, track_id, thumb=None, note=""):
        import datetime
        date = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        with self.lock, self._con() as c:
            cur = c.execute(
                "INSERT INTO events(cam,ts,date,cls,label,conf,track_id,thumb,note)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (cam, ts, date, cls, label, conf, track_id, thumb, note))
            return cur.lastrowid

    def search(self, cam=None, label=None, date=None, q=None, limit=100, offset=0):
        sql = "SELECT id,cam,ts,date,cls,label,conf,track_id,thumb,note FROM events WHERE 1=1"
        args = []
        if cam:
            sql += " AND cam=?"; args.append(cam)
        if label:
            sql += " AND label=?"; args.append(label)
        if date:
            sql += " AND date=?"; args.append(date)
        if q:
            sql += " AND (label LIKE ? OR note LIKE ? OR cam LIKE ?)"
            args += [f"%{q}%", f"%{q}%", f"%{q}%"]
        sql += " ORDER BY ts DESC LIMIT ? OFFSET ?"
        args += [limit, offset]
        with self.lock, self._con() as c:
            rows = c.execute(sql, args).fetchall()
        return [dict(zip(["id", "cam", "ts", "date", "cls", "label",
                          "conf", "track_id", "thumb", "note"], r)) for r in rows]

    def counts(self):
        with self.lock, self._con() as c:
            n = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            per = c.execute("SELECT label,COUNT(*) FROM events GROUP BY label ORDER BY 2 DESC LIMIT 12").fetchall()
            cams = c.execute("SELECT cam,COUNT(*) FROM events GROUP BY cam").fetchall()
        return {"total": n, "by_label": per, "by_cam": cams}

    def thumb_path(self, cam, eid) -> Path:
        p = DATA / "thumbs" / cam
        p.mkdir(parents=True, exist_ok=True)
        return p / f"{eid}.jpg"

    def prune(self, max_days=30, max_events=20000):
        """Auto-delete old events to keep disk usage under control."""
        import time as _t
        cutoff = _t.time() - max_days * 86400
        with self.lock, self._con() as c:
            old = c.execute("SELECT thumb FROM events WHERE ts<?", (cutoff,)).fetchall()
            c.execute("DELETE FROM events WHERE ts<?", (cutoff,))
            n = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            if n > max_events:
                c.execute(f"DELETE FROM events WHERE id IN (SELECT id FROM events ORDER BY ts ASC LIMIT {n - max_events})")
        for (th,) in old:
            try:
                if th: Path(th).unlink(missing_ok=True)
            except Exception:
                pass
