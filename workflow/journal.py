"""Local intent/evidence journal. Does not create tasks, claims or process handles.

Caller owns BEGIN IMMEDIATE / commit / rollback. Lost results remain unknown.
The selected authority and dispatcher remain responsible for actual operations.
"""
import hashlib
import json
from workflow.contract import Refusal, canonical, check_config, validate
from workflow.notifications import ProjectACL, append_notification, install_schema, make_envelope


def _transaction(db):
    if not db.in_transaction: raise Refusal("caller-transaction-required")


def install(db, config):
    """Explicit new local journal only. Never invoked implicitly by prepare."""
    check_config(config)
    db.execute("CREATE TABLE IF NOT EXISTS factory_binding (singleton INTEGER PRIMARY KEY CHECK(singleton=1), config TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS factory_intents (key TEXT PRIMARY KEY, envelope TEXT NOT NULL, digest TEXT NOT NULL, status TEXT NOT NULL, receipt TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS factory_observations (key TEXT NOT NULL, digest TEXT NOT NULL, status TEXT NOT NULL, receipt TEXT NOT NULL, PRIMARY KEY(key,digest))")
    db.execute("INSERT OR IGNORE INTO factory_binding VALUES(1,?)", (canonical(config),))
    _binding(db, config)
    install_schema(db)


def _binding(db, config):
    check_config(config)
    row = db.execute("SELECT config FROM factory_binding WHERE singleton=1").fetchone()
    if not row or row[0] != canonical(config): raise Refusal("run-binding-changed-reconcile-before-cutover")


def _decode(config, key, encoded, digest):
    e = json.loads(encoded)
    if not isinstance(e, dict) or hashlib.sha256(canonical(e).encode()).hexdigest() != digest or e.get("key") != key:
        raise Refusal("stored-intent-integrity")
    return validate(e, config)


def _notice(db, config, e, status, payload):
    acl = ProjectACL({config["project"]: (config["project"], config["repo_id"], str(config["authority"]["epoch"]))})
    notice = make_envelope(scope=config["project"], project=config["project"],
        repository_id=config["repo_id"], authority_epoch=str(config["authority"]["epoch"]),
        task=e["task"]["id"], revision=e["task"]["revision"],
        event_id=e["key"] + "." + status, payload=payload)
    append_notification(db, notice, acl)


def prepare(db, config, e):
    _transaction(db); _binding(db, config); validate(e, config)
    encoded = canonical(e); digest = hashlib.sha256(encoded.encode()).hexdigest()
    old = db.execute("SELECT digest,status,envelope FROM factory_intents WHERE key=?", (e["key"],)).fetchone()
    if old:
        _decode(config, e["key"], old[2], old[0])
        if old[0] != digest: raise Refusal("idempotency-payload-conflict")
        return old[1]
    db.execute("INSERT INTO factory_intents VALUES(?,?,?,'pending',NULL)", (e["key"], encoded, digest))
    _notice(db, config, e, "pending", {"kind": "intent-pending", "operation": e["operation"]})
    return "pending"


def settle(db, config, key, status, receipt):
    """Record operator/adapter evidence, never interpret it as claim permission.

    Pending/unknown entries need authority read-by-key and dispatcher/native
    reconciliation. This recorder refuses to overwrite an uncertain outcome;
    a separately reviewed reconciliation mapping is required to resolve it.
    """
    _transaction(db); _binding(db, config)
    if status not in {"confirmed", "refused", "unknown"} or not isinstance(receipt, dict):
        raise Refusal("receipt-contract")
    encoded = canonical(receipt)
    if len(encoded.encode()) > 65536: raise Refusal("receipt-limit")
    row = db.execute("SELECT envelope,status,receipt,digest FROM factory_intents WHERE key=?", (key,)).fetchone()
    if not row: raise Refusal("unknown-intent")
    e = _decode(config, key, row[0], row[3])
    if row[1] != "started":
        if row[1] == status and row[2] == encoded: return status
        raise Refusal("receipt-conflict-reconciliation-required")
    db.execute("UPDATE factory_intents SET status=?,receipt=? WHERE key=? AND status='started'", (status, encoded, key))
    _notice(db, config, e, status, {"kind": "intent-observation", "operation": e["operation"], "status": status})
    return status


def observe(db, config, key, status, receipt):
    """Append local evidence without settling or hiding an unresolved owner intent."""
    _transaction(db); _binding(db, config)
    if status not in {"confirmed", "refused", "unknown"} or not isinstance(receipt, dict):
        raise Refusal("observation-contract")
    if not db.execute("SELECT 1 FROM factory_intents WHERE key=?", (key,)).fetchone():
        raise Refusal("unknown-intent")
    encoded = canonical(receipt)
    if len(encoded.encode()) > 65536: raise Refusal("observation-limit")
    digest = hashlib.sha256(canonical([status, receipt]).encode()).hexdigest()
    db.execute("INSERT OR IGNORE INTO factory_observations VALUES(?,?,?,?)", (key, digest, status, encoded))
    return "evidence-recorded-intent-unchanged"


def pending(db, config):
    _binding(db, config)
    rows = db.execute("SELECT key,envelope,status,receipt,digest FROM factory_intents WHERE status IN ('pending','started','unknown') ORDER BY key").fetchall()
    return [{"envelope": _decode(config, key, e, digest), "status": s, "receipt": json.loads(r) if r else None,
             "next": "read-authority-by-key-and-existing-dispatcher-journal"} for key, e, s, r, digest in rows]


def start(db, config, key):
    """CAS intent before invoking an existing owner bridge; commit before call.

    A surviving started intent is uncertain and can never be started again here.
    It requires owner reconciliation, even if no runtime effect actually happened.
    """
    _transaction(db); _binding(db, config)
    row = db.execute("SELECT envelope,status,digest FROM factory_intents WHERE key=?", (key,)).fetchone()
    if not row or row[1] != "pending": raise Refusal("already-started-or-unknown-reconcile")
    e = _decode(config, key, row[0], row[2])
    changed = db.execute("UPDATE factory_intents SET status='started' WHERE key=? AND status='pending'", (key,)).rowcount
    if changed != 1: raise Refusal("start-cas-conflict")
    _notice(db, config, e, "started", {"kind": "intent-started", "operation": e["operation"]})
    return e
