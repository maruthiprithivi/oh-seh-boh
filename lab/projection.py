"""Mock eventual GitHub projection: local SQLite sink, no remote writes."""
import json
import sqlite3


class MockProjection:
    def __init__(self, path):
        self.path = path
        with sqlite3.connect(path) as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS seen(event_id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS tasks(scope TEXT,task TEXT,sequence INTEGER,payload TEXT,
              PRIMARY KEY(scope,task));
            """)

    def apply(self, event, fail_before=False, lose_reply=False):
        if fail_before:
            raise ConnectionError("synthetic projection outage")
        with sqlite3.connect(self.path) as db:
            if not db.execute("SELECT 1 FROM seen WHERE event_id=?", (event["event_id"],)).fetchone():
                payload = json.loads(event["payload"])
                task = payload.get("task")
                if task:
                    current = db.execute("SELECT sequence FROM tasks WHERE scope=? AND task=?", (event["scope"], task)).fetchone()
                    if not current or event["seq"] > current[0]:
                        db.execute("INSERT OR REPLACE INTO tasks VALUES(?,?,?,?)",
                                   (event["scope"], task, event["seq"], event["payload"]))
                db.execute("INSERT INTO seen VALUES(?)", (event["event_id"],))
        if lose_reply:
            raise TimeoutError("synthetic reply lost after sink commit")
