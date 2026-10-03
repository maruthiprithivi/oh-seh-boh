"""Subprocess client for the isolated OSB lab; no real transport identity claim."""
import json
from pathlib import Path
import subprocess
import sys
import time


def invoke(db, synthetic_actor, operation, payload, fault=None, timeout=5):
    args = [sys.executable, str(Path(__file__).with_name("backend.py")),
            "--db", str(db), "--synthetic-actor", synthetic_actor, "--test-only"]
    if fault:
        args += ["--fault", fault]
    envelope = {"protocol": "osb.lab.v1", "operation": operation, "payload": payload}
    start = time.perf_counter()
    process = subprocess.run(args, input=json.dumps(envelope), text=True,
                             capture_output=True, timeout=timeout, check=False)
    output = None
    if process.stdout.strip():
        output = json.loads(process.stdout)
    return {"exit": process.returncode, "receipt": output, "stderr": process.stderr,
            "elapsed_seconds": time.perf_counter() - start}


def invoke_existing_endpoint(client_handle, operation, payload, timeout=5):
    """Provisional integration transport. Supervisor supplies fixed command argv.

    Do not derive principal/DB from task JSON. Client handle is trusted isolated
    fixture configuration or an already approved fixed authenticated route.
    This only frames coord.project.v1; it proves neither compatibility nor SSH.
    """
    envelope = {"protocol": "coord.project.v1", "operation": operation, "payload": payload}
    encoded = json.dumps(envelope)
    if len(encoded.encode()) > 65536:
        raise ValueError("endpoint payload exceeds 64 KiB")
    if any(key in payload for key in ("principal", "actor", "caller")):
        raise ValueError("identity must be bound by the supervisor route")
    if operation not in ("scope-status", "authority-info") and not payload.get("authority_id"):
        raise ValueError("current authority identity is required")
    start = time.perf_counter()
    process = subprocess.run(list(client_handle), input=encoded, text=True,
                             capture_output=True, timeout=timeout, check=False)
    receipt = json.loads(process.stdout) if process.stdout.strip() else None
    return {"exit": process.returncode, "receipt": receipt, "stderr": process.stderr,
            "elapsed_seconds": time.perf_counter() - start,
            "granted": process.returncode == 0 and isinstance(receipt, dict) and receipt.get("ok") is True}
