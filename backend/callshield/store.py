import json
import sqlite3
from pathlib import Path
import time


class Store:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = root / "calls.db"
        self.path.touch(mode=0o600, exist_ok=True)
        self.path.chmod(0o600)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY, context TEXT NOT NULL,
                    consent INTEGER NOT NULL, finalized INTEGER NOT NULL DEFAULT 0, summary TEXT,
                    created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS segments(call_id TEXT NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
                    idx INTEGER NOT NULL, digest TEXT NOT NULL, status TEXT NOT NULL, result TEXT,
                    created REAL NOT NULL, PRIMARY KEY(call_id, idx));
            """)
            db.execute("UPDATE segments SET status='failed' WHERE status='processing'")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def init(self, call_id, context, consent):
        encoded = json.dumps(context, sort_keys=True)
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO calls(id,context,consent,created) VALUES(?,?,?,?)",
                (call_id, encoded, int(consent), time.time()),
            )
            row = db.execute("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone()
            return row["context"] == encoded and row["consent"] == int(consent)

    def call(self, call_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone()
            return dict(row) if row else None

    def reserve(self, call_id, index, digest):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            call = db.execute(
                "SELECT finalized FROM calls WHERE id=?", (call_id,)
            ).fetchone()
            if call is None or call["finalized"]:
                return "closed"
            row = db.execute(
                "SELECT * FROM segments WHERE call_id=? AND idx=?", (call_id, index)
            ).fetchone()
            if row:
                if row["digest"] != digest:
                    return "conflict"
                if row["status"] != "failed":
                    return row["status"]
                db.execute(
                    "UPDATE segments SET status='processing',result=NULL WHERE call_id=? AND idx=?",
                    (call_id, index),
                )
                return "new"
            count = db.execute(
                "SELECT COUNT(*) FROM segments WHERE call_id=?", (call_id,)
            ).fetchone()[0]
            if count >= 360:
                return "limit"
            db.execute(
                "INSERT INTO segments VALUES(?,?,?,'processing',NULL,?)",
                (call_id, index, digest, time.time()),
            )
            return "new"

    def complete(self, call_id, index, result, status="completed"):
        with self.connect() as db:
            db.execute(
                "UPDATE segments SET status=?,result=? WHERE call_id=? AND idx=?",
                (status, json.dumps(result, ensure_ascii=False), call_id, index),
            )

    def segments(self, call_id):
        with self.connect() as db:
            rows = db.execute(
                "SELECT idx,status,result FROM segments WHERE call_id=? ORDER BY idx",
                (call_id,),
            ).fetchall()
        return [
            {
                "segment_id": row["idx"],
                "status": row["status"],
                "result": json.loads(row["result"]) if row["result"] else None,
            }
            for row in rows
        ]

    def finalize(self, call_id, summary):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM segments WHERE call_id=? AND status='processing'",
                (call_id,),
            ).fetchone():
                return False
            db.execute(
                "UPDATE calls SET finalized=1,summary=? WHERE id=?",
                (json.dumps(summary, ensure_ascii=False), call_id),
            )
            return True

    def delete(self, call_id):
        with self.connect() as db:
            db.execute("DELETE FROM calls WHERE id=?", (call_id,))
