"""OSB Linux-only isolated reference backend; synthetic identities, never production.

Python/SQLite/flock only. No GitHub, LLM, SSH, or network calls. All files must
live in a disposable private directory. This source has not been executed.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
import uuid

PROTOCOL = "osb.lab.v1"
READS = {"status", "check", "events", "authority-info"}
SAFETY = {"revoke", "release", "ack", "recover", "reauthorize"}
SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE scopes(id TEXT PRIMARY KEY,team TEXT NOT NULL,repo_id TEXT UNIQUE NOT NULL,
 primary_actor TEXT NOT NULL,primary_epoch INTEGER NOT NULL DEFAULT 1);
CREATE TABLE members(scope TEXT,actor TEXT,role TEXT,epoch INTEGER,active INTEGER,
 PRIMARY KEY(scope,actor));
CREATE TABLE sessions(scope TEXT,actor TEXT,session TEXT,generation INTEGER,active INTEGER,
 PRIMARY KEY(scope,actor,session));
CREATE TABLE tasks(scope TEXT,id TEXT,resources TEXT,base TEXT,head TEXT,state TEXT,
 version INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(scope,id));
CREATE TABLE claims(scope TEXT,task TEXT,actor TEXT,session TEXT,generation INTEGER,
 fence INTEGER,authority TEXT,expires INTEGER,active INTEGER,recipient TEXT,
 PRIMARY KEY(scope,task));
CREATE TABLE requests(namespace TEXT,key TEXT,digest TEXT,result TEXT,
 PRIMARY KEY(namespace,key));
CREATE TABLE events(seq INTEGER PRIMARY KEY,event_id TEXT UNIQUE,scope TEXT,kind TEXT,
 payload TEXT NOT NULL);
CREATE TABLE acknowledgments(event_id TEXT,actor TEXT,PRIMARY KEY(event_id,actor));
CREATE TABLE effects(scope TEXT,id TEXT,state TEXT,head TEXT,PRIMARY KEY(scope,id));
CREATE TABLE protected_writes(id TEXT PRIMARY KEY,scope TEXT,task TEXT,actor TEXT,
 fence INTEGER,head TEXT,payload TEXT);
CREATE INDEX active_claims ON claims(scope,active,expires);
CREATE INDEX event_pages ON events(scope,seq);
"""


class Refusal(Exception):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class Engine:
    def __init__(self, path):
        self.path = Path(path)
        self.journal = self.path.with_suffix(".journal.jsonl")
        self.lock = self.path.with_suffix(".lock")
        self.marker = self.path.with_suffix(".marker.json")
        self.statements = []

    @classmethod
    def create(cls, path, max_pending=1000):
        """Trusted fixture setup only. Never overwrite an existing authority."""
        path = Path(path)
        if path.exists() or path.with_suffix(".journal.jsonl").exists():
            raise Refusal("fixture-already-exists")
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO meta VALUES(?,?)", [
            ("authority", str(uuid.uuid4())), ("sequence", "0"),
            ("fence", "0"), ("clock", "0"), ("max_pending", str(max_pending))])
        conn.commit()
        conn.close()
        engine = cls(path)
        engine.write_marker({"sequence": 0, "pending": None})
        return engine

    def write_marker(self, value):
        temp = self.marker.with_suffix(".new")
        with temp.open("w") as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, self.marker)
        directory = os.open(self.marker.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def write(self, sql, args=()):
        self.db.execute(sql, args)
        self.statements.append([sql, list(args)])

    def value(self, key):
        return self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()[0]

    def setvalue(self, key, value):
        self.write("UPDATE meta SET value=? WHERE key=?", (str(value), key))

    def append(self, record):
        with self.journal.open("a", encoding="utf-8") as stream:
            stream.write(canonical(record) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        if record["kind"] == "prepare":
            self.write_marker({"sequence": record["sequence"], "pending": record["id"]})
        elif record["kind"] in ("commit", "abandon"):
            marker = json.loads(self.marker.read_text())
            marker["pending"] = None
            self.write_marker(marker)

    def journal_state(self):
        prepared, committed = {}, set()
        if self.journal.exists():
            for line in self.journal.read_text().splitlines():
                row = json.loads(line)  # Torn/invalid journal refuses; never guess recovery.
                if row["kind"] == "prepare":
                    prepared[row["id"]] = row
                elif row["kind"] == "commit":
                    committed.add(row["id"])
                elif row["kind"] == "abandon":
                    prepared.pop(row["id"], None)
        pending = set(prepared) - committed
        confirmed = [prepared[key] for key in committed if key in prepared]
        return sorted(confirmed, key=lambda r: r["sequence"]), pending

    def event(self, scope, kind, payload):
        seq = int(self.value("sequence")) + 1
        self.setvalue("sequence", seq)
        event_id = str(uuid.uuid4())
        self.write("INSERT INTO events VALUES(?,?,?,?,?)",
                   (seq, event_id, scope, kind, canonical({**payload, "clock_ms": int(self.value("clock"))})))
        return {"event_id": event_id, "sequence": seq}

    def execute(self, actor, request, fault=None):
        """Actor is a synthetic fixture route, not real transport authentication."""
        if len(canonical(request).encode()) > 65536:
            return {"ok": False, "reason": "payload-limit"}
        if request.get("protocol") != PROTOCOL:
            return {"ok": False, "reason": "protocol"}
        if not isinstance(request.get("payload"), dict):
            return {"ok": False, "reason": "payload-object"}
        if any(k in request["payload"] for k in ("actor", "principal", "caller")):
            return {"ok": False, "reason": "identity-spoof"}
        if not self.path.is_file() or not self.marker.is_file():
            return {"ok": False, "reason": "missing-isolated-fixture"}
        started = time.monotonic()
        with self.lock.open("a") as lock:
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() - started >= 1:
                        return {"ok": False, "reason": "busy"}
                    time.sleep(0.01)
            self.db = sqlite3.connect(self.path, timeout=1)
            self.db.row_factory = sqlite3.Row
            self.statements = []
            try:
                self.db.execute("BEGIN IMMEDIATE")
                op = request["operation"]
                marker = json.loads(self.marker.read_text())
                if op != "recover" and (marker["pending"] or
                        marker["sequence"] > int(self.value("sequence"))):
                    raise Refusal("recovery-required")
                result = self.apply(actor, op, request["payload"])
                if self.statements:
                    txid = str(uuid.uuid4())
                    self.append({"kind": "prepare", "id": txid,
                                 "sequence": int(self.value("sequence")),
                                 "statements": self.statements})
                    if fault == "before-commit":
                        os._exit(72)
                    self.db.commit()
                    self.append({"kind": "commit", "id": txid})
                    if fault == "after-commit":
                        os._exit(73)
                else:
                    self.db.commit()
                return result
            except Refusal as exc:
                self.db.rollback()
                return {"ok": False, "reason": str(exc)}
            except (OSError, sqlite3.Error, ValueError, KeyError, TypeError):
                self.db.rollback()
                return {"ok": False, "reason": "invalid-or-storage-failure"}
            finally:
                self.db.close()

    def apply(self, actor, op, p):
        authority = self.value("authority")
        if op == "authority-info":
            return {"ok": True, "protocol": PROTOCOL, "authority_id": authority}
        if op == "recover":
            if actor != "lab-admin" or p.get("confirm") != "ISOLATED_LAB_RECOVERY":
                raise Refusal("admin-required")
            confirmed, pending = self.journal_state()
            before = int(self.value("sequence"))
            for entry in confirmed:
                if entry["sequence"] > before:
                    for sql, params in entry["statements"]:
                        # Redo is already in the original confirmed journal entry.
                        # Do not re-journal historical INSERTs in recovery's own entry.
                        self.db.execute(sql, params)
            # Unconfirmed transactions need explicit operator abandonment in this lab.
            if pending and not p.get("abandon_unconfirmed"):
                raise Refusal("unknown-transaction-review-required")
            for txid in pending:
                self.append({"kind": "abandon", "id": txid})
            self.setvalue("authority", str(uuid.uuid4()))
            self.write("UPDATE claims SET active=0")
            self.write("UPDATE sessions SET active=0")
            self.write("UPDATE members SET active=0,epoch=epoch+1")
            self.write("UPDATE scopes SET primary_epoch=primary_epoch+1")
            self.setvalue("fence", int(self.value("fence")) + 10)
            return {"ok": True, "authority_id": self.value("authority"),
                    **self.event("@admin", "recovery", {"quarantined": True})}
        if op == "configure":
            if actor != "lab-admin":
                raise Refusal("admin-required")
            if p["members"].get(p["primary"]) not in ("admin", "writer") or "admin" not in p["members"].values():
                raise Refusal("explicit-primary-and-admin-required")
            self.write("INSERT INTO scopes(id,team,repo_id,primary_actor) VALUES(?,?,?,?)",
                       (p["scope"], p["team"], p["repo_id"], p["primary"]))
            for member, role in p["members"].items():
                if role not in ("reader", "writer", "admin"):
                    raise Refusal("invalid-role")
                self.write("INSERT INTO members VALUES(?,?,?,?,1)",
                           (p["scope"], member, role, 1))
            return {"ok": True, **self.event(p["scope"], "configured", {})}
        if op == "tick":
            if actor != "lab-admin" or type(p.get("milliseconds")) is not int or p["milliseconds"] < 0:
                raise Refusal("admin-clock-required")
            self.setvalue("clock", int(self.value("clock")) + p["milliseconds"])
            return {"ok": True, **self.event("@admin", "clock", {})}
        if p.get("authority_id") != authority:
            raise Refusal("stale-authority")
        scope = self.db.execute("SELECT * FROM scopes WHERE id=?", (p["scope"],)).fetchone()
        member = self.db.execute("SELECT * FROM members WHERE scope=? AND actor=?",
                                 (p["scope"], actor)).fetchone()
        if op == "reauthorize" and actor == "lab-admin":
            self.write("UPDATE members SET active=1 WHERE scope=?", (p["scope"],))
            return {"ok": True, **self.event(p["scope"], "reauthorized", {})}
        if not scope or not member or not member["active"]:
            raise Refusal("unauthorized-scope")
        if p.get("repo_id", scope["repo_id"]) != scope["repo_id"]:
            raise Refusal("wrong-repository")
        if op == "status":
            return {"ok": True, "authority_id": authority,
                    "membership_epoch": member["epoch"], "primary": scope["primary_actor"],
                    "primary_epoch": scope["primary_epoch"],
                    "tasks": [dict(r) for r in self.db.execute(
                        "SELECT * FROM tasks WHERE scope=? ORDER BY id LIMIT 100", (p["scope"],))]}
        if p.get("membership_epoch") != member["epoch"]:
            raise Refusal("stale-membership")
        if op == "events":
            limit = p.get("limit", 100)
            if type(limit) is not int or not 1 <= limit <= 100:
                raise Refusal("page-limit")
            return {"ok": True, "events": [dict(r) for r in self.db.execute(
                "SELECT * FROM events WHERE scope=? AND seq>? ORDER BY seq LIMIT ?",
                (p["scope"], p.get("after_seq", 0), limit))]}
        if member["role"] == "reader" and op != "ack":
            raise Refusal("writer-required")
        namespace = canonical([authority, p["scope"], actor, member["epoch"]])
        if op != "check":
            key = p.get("request_id")
            if not isinstance(key, str) or not 1 <= len(key) <= 128:
                raise Refusal("request-id-required")
            digest = hashlib.sha256(canonical([op, p]).encode()).hexdigest()
            previous = self.db.execute("SELECT * FROM requests WHERE namespace=? AND key=?",
                                       (namespace, key)).fetchone()
            if previous:
                if previous["digest"] != digest:
                    raise Refusal("idempotency-conflict")
                return json.loads(previous["result"])
            pending_count = self.db.execute("SELECT count(*) FROM events e WHERE e.scope=? AND e.kind!='ack' AND NOT EXISTS "
                "(SELECT 1 FROM acknowledgments a WHERE a.event_id=e.event_id AND a.actor=?)",
                (p["scope"], scope["primary_actor"])).fetchone()[0]
            if op not in SAFETY and pending_count >= int(self.value("max_pending")):
                raise Refusal("backpressure")
        result = self.transition(actor, scope, op, p)
        if op != "check":
            result.update(self.event(p["scope"], op, {"actor": actor, "task": p.get("task"),
                "target": p.get("target"), "session": p.get("session"),
                "fence": result.get("fence", p.get("fence")), "result": dict(result)}))
            self.write("INSERT INTO requests VALUES(?,?,?,?)", (namespace, key, digest, canonical(result)))
        return result

    def transition(self, actor, scope, op, p):
        sid = scope["id"]
        now = int(self.value("clock"))
        if op == "ack":
            row = self.db.execute("SELECT scope FROM events WHERE event_id=?", (p["event_id"],)).fetchone()
            if not row or row[0] != sid:
                raise Refusal("wrong-event-scope")
            self.write("INSERT OR IGNORE INTO acknowledgments VALUES(?,?)", (p["event_id"], actor))
            return {"ok": True}
        if op in ("revoke", "primary-transfer"):
            target = self.db.execute("SELECT * FROM members WHERE scope=? AND actor=?",
                                     (sid, p["target"])).fetchone()
            if not target or not target["active"]:
                raise Refusal("inactive-target")
            if op == "revoke":
                caller = self.db.execute("SELECT role FROM members WHERE scope=? AND actor=?", (sid, actor)).fetchone()[0]
                if caller != "admin" or p["target"] == scope["primary_actor"]:
                    raise Refusal("admin-or-primary-transfer-required")
                admins = self.db.execute("SELECT count(*) FROM members WHERE scope=? AND role='admin' AND active=1", (sid,)).fetchone()[0]
                if target["role"] == "admin" and admins == 1:
                    raise Refusal("last-admin")
                self.write("UPDATE members SET active=0,epoch=epoch+1 WHERE scope=? AND actor=?", (sid, p["target"]))
                self.write("UPDATE sessions SET active=0 WHERE scope=? AND actor=?", (sid, p["target"]))
                self.write("UPDATE claims SET active=0 WHERE scope=? AND actor=?", (sid, p["target"]))
                return {"ok": True}
            if actor != scope["primary_actor"] or p.get("primary_epoch") != scope["primary_epoch"]:
                raise Refusal("stale-or-wrong-primary")
            if target["role"] not in ("writer", "admin"):
                raise Refusal("primary-writer-required")
            if self.db.execute("SELECT 1 FROM effects WHERE scope=? AND state IN ('attempting','unknown')", (sid,)).fetchone():
                raise Refusal("effect-slot-occupied")
            self.write("UPDATE scopes SET primary_actor=?,primary_epoch=primary_epoch+1 WHERE id=?", (p["target"], sid))
            return {"ok": True, "primary_epoch": scope["primary_epoch"] + 1}
        if op in ("effect-intent", "effect-result"):
            if actor != scope["primary_actor"] or p.get("primary_epoch") != scope["primary_epoch"]:
                raise Refusal("stale-or-wrong-primary")
            if op == "effect-intent":
                if self.db.execute("SELECT 1 FROM effects WHERE scope=? AND state IN ('attempting','unknown')", (sid,)).fetchone():
                    raise Refusal("effect-slot-occupied")
                self.write("INSERT INTO effects VALUES(?,?,?,?)", (sid, p["effect_id"], "attempting", p["head"]))
            else:
                if p["outcome"] not in ("merged", "refused", "unknown"):
                    raise Refusal("invalid-effect-outcome")
                row = self.db.execute("SELECT * FROM effects WHERE scope=? AND id=?", (sid, p["effect_id"])).fetchone()
                if not row or row["head"] != p["head"]:
                    raise Refusal("effect-revision-mismatch")
                self.write("UPDATE effects SET state=? WHERE scope=? AND id=?", (p["outcome"], sid, p["effect_id"]))
            return {"ok": True}
        if op == "session":
            generation = self.db.execute("SELECT coalesce(max(generation),0)+1 FROM sessions WHERE scope=? AND actor=?",
                                         (sid, actor)).fetchone()[0]
            self.write("UPDATE sessions SET active=0 WHERE scope=? AND actor=?", (sid, actor))
            self.write("UPDATE claims SET active=0 WHERE scope=? AND actor=?", (sid, actor))
            self.write("INSERT INTO sessions VALUES(?,?,?,?,1)", (sid, actor, p["session"], generation))
            return {"ok": True, "generation": generation}
        session = self.db.execute("SELECT * FROM sessions WHERE scope=? AND actor=? AND session=?",
                                  (sid, actor, p["session"])).fetchone()
        if not session or not session["active"] or session["generation"] != p["generation"]:
            raise Refusal("stale-session")
        if op == "intent":
            if not all(isinstance(p.get(k), str) and re.fullmatch(r"[0-9a-f]{40}", p[k]) for k in ("base", "head")):
                raise Refusal("full-sha1-revision-required")
            resources = normalize_resources(p["resources"])
            self.write("INSERT INTO tasks(scope,id,resources,base,head,state) VALUES(?,?,?,?,?,?)",
                       (sid, p["task"], canonical(resources), p["base"], p["head"], "open"))
            return {"ok": True, "version": 1}
        task = self.db.execute("SELECT * FROM tasks WHERE scope=? AND id=?", (sid, p["task"])).fetchone()
        if not task:
            raise Refusal("unknown-task")
        claim = self.db.execute("SELECT * FROM claims WHERE scope=? AND task=?", (sid, p["task"])).fetchone()
        if op == "claim":
            if p.get("expected_version") != task["version"]:
                raise Refusal("stale-version")
            if claim and claim["active"] and claim["expires"] > now:
                raise Refusal("scope-conflict")
            for row in self.db.execute("SELECT c.*,t.resources FROM claims c JOIN tasks t ON t.scope=c.scope AND t.id=c.task "
                                       "WHERE c.scope=? AND c.active=1 AND c.expires>?", (sid, now)):
                if overlaps(json.loads(row["resources"]), json.loads(task["resources"])):
                    raise Refusal("scope-conflict")
            fence = int(self.value("fence")) + 1
            self.setvalue("fence", fence)
            ttl = p.get("ttl_ms", 900000)
            if type(ttl) is not int or not 1 <= ttl <= 86400000:
                raise Refusal("ttl-limit")
            self.write("INSERT OR REPLACE INTO claims VALUES(?,?,?,?,?,?,?,?,1,NULL)",
                (sid, p["task"], actor, p["session"], p["generation"], fence, self.value("authority"), now + ttl))
            self.write("UPDATE tasks SET state='claimed',version=version+1 WHERE scope=? AND id=?", (sid, p["task"]))
            return {"ok": True, "fence": fence, "expires_ms": now + ttl, "version": task["version"] + 1,
                    "resources": json.loads(task["resources"]),
                    "authority_id": self.value("authority")}
        if op == "handoff-accept":
            if not claim or claim["recipient"] != actor:
                raise Refusal("wrong-recipient")
        elif not claim or claim["actor"] != actor or claim["session"] != p["session"]:
            raise Refusal("wrong-holder")
        if not claim["active"] or claim["expires"] <= now or claim["fence"] != p.get("fence") or claim["authority"] != self.value("authority"):
            raise Refusal("expired-or-stale-fence")
        if op == "check":
            return {"ok": True, "fence": claim["fence"], "expires_ms": claim["expires"]}
        if op != "check" and (p.get("head") != task["head"] or p.get("base") != task["base"]):
            raise Refusal("revision-mismatch")
        if op == "heartbeat":
            self.write("UPDATE claims SET expires=? WHERE scope=? AND task=?", (now + 900000, sid, p["task"]))
            return {"ok": True, "fence": claim["fence"], "expires_ms": now + 900000}
        if op == "protected-write":
            effect_key = hashlib.sha256(canonical([self.value("authority"), sid, actor,
                                                   p["membership_epoch"], p["request_id"]]).encode()).hexdigest()
            self.write("INSERT INTO protected_writes VALUES(?,?,?,?,?,?,?)",
                       (effect_key, sid, p["task"], actor, claim["fence"], task["head"],
                        canonical(p.get("content", {}))))
            return {"ok": True, "fence": claim["fence"]}
        if op in ("release", "complete"):
            self.write("UPDATE claims SET active=0 WHERE scope=? AND task=?", (sid, p["task"]))
            self.write("UPDATE tasks SET state=?,version=version+1 WHERE scope=? AND id=?",
                       ("ready_for_review" if op == "complete" else "open", sid, p["task"]))
            return {"ok": True}
        if op == "handoff-offer":
            recipient = self.db.execute("SELECT * FROM members WHERE scope=? AND actor=?", (sid, p["target"])).fetchone()
            if not recipient or not recipient["active"] or recipient["role"] == "reader":
                raise Refusal("invalid-recipient")
            self.write("UPDATE claims SET recipient=? WHERE scope=? AND task=?", (p["target"], sid, p["task"]))
            return {"ok": True, "holder_unchanged": True}
        if op == "handoff-accept":
            fence = int(self.value("fence")) + 1
            self.setvalue("fence", fence)
            self.write("UPDATE claims SET actor=?,session=?,generation=?,fence=?,recipient=NULL WHERE scope=? AND task=?",
                       (actor, p["session"], p["generation"], fence, sid, p["task"]))
            return {"ok": True, "fence": fence}
        raise Refusal("unsupported-operation")


def normalize_resources(resources):
    if not isinstance(resources, list) or not 1 <= len(resources) <= 100:
        raise Refusal("resource-limit")
    output = []
    for resource in resources:
        kind, name = resource["type"], resource["name"]
        if kind not in ("repository", "file", "directory") or not isinstance(name, str) or not name or len(name) > 1024 or any(ord(c) < 32 for c in name):
            raise Refusal("invalid-resource")
        if name.startswith("/") or "\\" in name or any(p in (".", "..", "") for p in name.split("/")):
            raise Refusal("invalid-path")
        output.append({"type": kind, "name": name})
    return sorted(output, key=lambda r: (r["type"], r["name"]))


def overlaps(left, right):
    for a in left:
        for b in right:
            if "repository" in (a["type"], b["type"]) or a["name"] == b["name"]:
                return True
            if a["type"] == "directory" and b["name"].startswith(a["name"] + "/"):
                return True
            if b["type"] == "directory" and a["name"].startswith(b["name"] + "/"):
                return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--synthetic-actor", required=True)
    parser.add_argument("--fault", choices=("before-commit", "after-commit"))
    parser.add_argument("--test-only", required=True, action="store_true")
    args = parser.parse_args()
    request = json.loads(sys.stdin.buffer.read(65537))
    result = Engine(args.db).execute(args.synthetic_actor, request, args.fault)
    print(canonical(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
