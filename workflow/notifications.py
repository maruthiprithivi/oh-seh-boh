"""Optional notification helpers; no authority transitions or dispatcher here.

The authority owner must map append_notification into its existing transaction.
Every mutation requires a caller-owned transaction and never commits or rolls back.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from types import MappingProxyType


PROTOCOL = "osb.factory.notification.v1"
FIELDS = frozenset(("protocol", "scope", "project", "repository_id",
                    "authority_epoch", "task", "revision", "event_id",
                    "payload", "payload_digest"))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _validate(envelope):
    if not isinstance(envelope, dict) or set(envelope) != FIELDS:
        raise ValueError("exact versioned envelope fields required")
    if envelope["protocol"] != PROTOCOL:
        raise ValueError("unsupported notification protocol")
    for key in ("scope", "project", "repository_id", "authority_epoch", "task", "event_id"):
        if not isinstance(envelope[key], str) or not envelope[key].strip() or len(envelope[key]) > 512:
            raise ValueError("nonempty bounded identity required: " + key)
    revision = envelope["revision"]
    if type(revision) is not int or revision < 0:
        raise ValueError("revision must be a nonnegative integer")
    if not isinstance(envelope["payload"], dict):
        raise ValueError("payload must be an object")
    if envelope["payload_digest"] != _digest(envelope["payload"]):
        raise ValueError("payload digest mismatch")
    if len(_canonical(envelope).encode("utf-8")) > 65536:
        raise ValueError("notification exceeds 64 KiB")


def make_envelope(*, scope, project, repository_id, authority_epoch, task,
                  revision, event_id, payload):
    # Canonical roundtrip snapshots the caller's payload; later edits do not leak in.
    envelope = dict(protocol=PROTOCOL, scope=scope, project=project,
                    repository_id=repository_id, authority_epoch=authority_epoch,
                    task=task, revision=revision, event_id=event_id,
                    payload=json.loads(_canonical(payload)), payload_digest=_digest(payload))
    _validate(envelope)
    return envelope


class ProjectACL:
    """Trusted operator mapping: project -> (scope, repository_id, authority_epoch).

    Never construct this mapping from an envelope, queue, or GitHub projection.
    It is a local admission boundary, not an authentication implementation.
    """
    def __init__(self, projects):
        snapshot = {}
        for project, route in projects.items():
            if not isinstance(project, str) or not project.strip():
                raise ValueError("invalid project ACL key")
            if not isinstance(route, (tuple, list)) or len(route) != 3 or any(not isinstance(x, str) or not x.strip() for x in route):
                raise ValueError("ACL route requires scope, repository ID and epoch")
            snapshot[project] = tuple(route)
        self.projects = MappingProxyType(snapshot)

    def require(self, envelope):
        _validate(envelope)
        route = (envelope["scope"], envelope["repository_id"], envelope["authority_epoch"])
        if self.projects.get(envelope["project"]) != route:
            raise PermissionError("notification outside trusted project route")


def _transaction(connection):
    if not connection.in_transaction:
        raise RuntimeError("caller-owned transaction required; helper does not commit")


def install_schema(connection):
    """Explicit operator/owner migration only; never called by other helpers.

    execute (not executescript) preserves any existing caller transaction.
    """
    connection.execute("""CREATE TABLE IF NOT EXISTS factory_notification_outbox (
        project TEXT NOT NULL, event_id TEXT NOT NULL,
        envelope TEXT NOT NULL, event_digest TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','delivered','dead')),
        attempt INTEGER NOT NULL DEFAULT 0 CHECK(attempt >= 0),
        available_at REAL NOT NULL DEFAULT 0,
        last_error TEXT NOT NULL DEFAULT '',
        PRIMARY KEY(project, event_id)
    )""")


def append_notification(connection, envelope, acl):
    """Append in the SAME transaction as the authoritative transition.

    Return False for an identical retry. Conflicting identity reuse is refused.
    No background migration, broker publication, or authority write occurs here.
    """
    _transaction(connection)
    acl.require(envelope)
    encoded, digest = _canonical(envelope), _digest(envelope)
    existing = connection.execute(
        "SELECT event_digest FROM factory_notification_outbox WHERE project=? AND event_id=?",
        (envelope["project"], envelope["event_id"])).fetchone()
    if existing:
        if existing[0] != digest:
            raise ValueError("event identity already has different immutable content")
        return False
    connection.execute(
        "INSERT INTO factory_notification_outbox(project,event_id,envelope,event_digest) VALUES(?,?,?,?)",
        (envelope["project"], envelope["event_id"], encoded, digest))
    return True


def _bounds(now, limit=100, max_attempts=5, lease_seconds=60):
    if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
        raise ValueError("finite nonnegative owner clock required")
    for value, ceiling in ((limit, 1000), (max_attempts, 1000)):
        if type(value) is not int or not 1 <= value <= ceiling:
            raise ValueError("positive bounded integer required")
    if type(lease_seconds) not in (int, float) or not math.isfinite(lease_seconds) or not 0 < lease_seconds <= 86400:
        raise ValueError("lease must be positive and at most one day")


def poll_pending(connection, acl, *, now, limit=100):
    """Read-only broker-free notification polling; consumers reconcile authority.

    Does not allocate attempts. Use acquire_pending for outbound queue delivery.
    Filters each route before applying the result limit, including authority epoch.
    """
    _bounds(now, limit)
    result = []
    for project in sorted(acl.projects):
        rows = connection.execute(
            "SELECT event_id,envelope,event_digest FROM factory_notification_outbox "
            "WHERE project=? AND status='pending' AND available_at<=? ORDER BY event_id",
            (project, now))
        for event_id, encoded, digest in rows:
            envelope = json.loads(encoded)
            try:
                acl.require(envelope)
            except PermissionError:
                continue
            if envelope["project"] != project or envelope["event_id"] != event_id:
                raise ValueError("stored event index identity mismatch")
            if _digest(envelope) != digest:
                raise ValueError("stored event digest mismatch")
            result.append(envelope)
            if len(result) >= limit:
                return result
    return result


@dataclass(frozen=True)
class Delivery:
    envelope: dict
    event_digest: str
    attempt: int


def acquire_pending(connection, acl, *, now, limit=100, max_attempts=5, lease_seconds=60):
    """Allocate bounded delivery attempts in a short caller transaction.

    Commit before calling an injected transport. SQLite concurrent writers must
    use the owner's busy/retry policy (normally BEGIN IMMEDIATE). A stale snapshot
    lock error is propagated; it must not be treated as successful acquisition.
    """
    _transaction(connection)
    _bounds(now, limit, max_attempts, lease_seconds)
    result = []
    for envelope in poll_pending(connection, acl, now=now, limit=limit):
        key = (envelope["project"], envelope["event_id"])
        digest = _digest(envelope)
        row = connection.execute(
            "SELECT attempt FROM factory_notification_outbox WHERE project=? AND event_id=?", key).fetchone()
        attempt = row[0]
        if attempt >= max_attempts:
            connection.execute(
                "UPDATE factory_notification_outbox SET status='dead',last_error='attempt budget exhausted' "
                "WHERE project=? AND event_id=? AND status='pending' AND attempt=? AND event_digest=?",
                (*key, attempt, digest))
            continue
        changed = connection.execute(
            "UPDATE factory_notification_outbox SET attempt=attempt+1,available_at=? "
            "WHERE project=? AND event_id=? AND status='pending' AND attempt=? "
            "AND event_digest=? AND available_at<=?",
            (now + lease_seconds, *key, attempt, digest, now)).rowcount
        if changed == 1:
            result.append(Delivery(envelope, digest, attempt + 1))
    return result


def _delivery_key(delivery, acl):
    acl.require(delivery.envelope)
    if type(delivery.attempt) is not int or delivery.attempt < 1:
        raise ValueError("positive delivery attempt required")
    return (delivery.envelope["project"], delivery.envelope["event_id"])


def acknowledge(connection, delivery, acl):
    """CAS acknowledgment by complete event digest AND allocated attempt.

    Duplicate acknowledgment of the same completed attempt returns True. Old or
    mismatched acknowledgments return False; they never finish a later attempt.
    """
    _transaction(connection)
    key = _delivery_key(delivery, acl)
    if _digest(delivery.envelope) != delivery.event_digest:
        return False
    changed = connection.execute(
        "UPDATE factory_notification_outbox SET status='delivered',last_error='' "
        "WHERE project=? AND event_id=? AND status='pending' AND event_digest=? AND attempt=?",
        (*key, delivery.event_digest, delivery.attempt)).rowcount
    if changed:
        return True
    return connection.execute(
        "SELECT 1 FROM factory_notification_outbox WHERE project=? AND event_id=? "
        "AND status='delivered' AND event_digest=? AND attempt=?",
        (*key, delivery.event_digest, delivery.attempt)).fetchone() is not None


def reject_delivery(connection, delivery, acl, *, now, max_attempts=5, retry_seconds=60, error=""):
    """CAS a failed attempt to retry or dead letter; no rows or authority deleted."""
    _transaction(connection)
    _bounds(now, max_attempts=max_attempts, lease_seconds=retry_seconds)
    key = _delivery_key(delivery, acl)
    if _digest(delivery.envelope) != delivery.event_digest:
        return False
    # Operator-provided bounded reason only. Do not include credentials or payloads.
    if not isinstance(error, str):
        raise ValueError("error must be operator-sanitized text")
    status = "dead" if delivery.attempt >= max_attempts else "pending"
    return connection.execute(
        "UPDATE factory_notification_outbox SET status=?,available_at=?,last_error=? "
        "WHERE project=? AND event_id=? AND status='pending' AND event_digest=? AND attempt=?",
        (status, now + retry_seconds, error[:512], *key, delivery.event_digest, delivery.attempt)).rowcount == 1


def reconcile(envelope, acl, authority_reader):
    """Read CURRENT authority, never infer work/grants/state from queue payload.

    Reader must be the owner's authenticated, epoch-bound read and implement its
    own unavailable-route refusal / uncertain-effect recovery. This helper neither
    launches workers nor changes authority, workflow state or GitHub projection.
    """
    acl.require(envelope)
    return authority_reader(**{key: envelope[key] for key in
                              ("scope", "project", "repository_id", "authority_epoch", "task")})


class LightweightQueue:
    """Optional self-host transport seam; injected operator send only."""
    def __init__(self, operator_send):
        if not callable(operator_send):
            raise TypeError("operator transport callable required")
        self.operator_send = operator_send

    def send(self, delivery, acl):
        _delivery_key(delivery, acl)
        if _digest(delivery.envelope) != delivery.event_digest:
            raise ValueError("delivery digest mismatch")
        # No implicit acknowledgment: transport acceptance is not consumption.
        return self.operator_send(json.loads(_canonical(delivery.envelope)))


class CloudflareQueues(LightweightQueue):
    """Cloudflare Queues seam using an existing admitted operator callable.

    No SDK, credentials, HTTP, queue creation or provider grants. An operator may
    inject its pre-existing send API; destination and auth stay in that transport.
    """
