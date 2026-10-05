"""GCP-test-only relay: execute native orch, lose only a successful record ACK.

No fake store, publisher, authority or runner mutation. Never a production route.
"""
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    if sys.platform != "linux" or os.environ.get("OSB_NATIVE_TEST_RELAY") != "admitted-gcp-only":
        raise ValueError("separately admitted GCP test relay only")
    bun, orch, audit, *arguments = sys.argv[1:]
    if not all(Path(value).is_absolute() for value in (bun, orch, audit)):
        raise ValueError("absolute native binaries and audit path required")
    is_record = len(arguments) >= 7 and arguments[:1] == ["--store"] and arguments[2:4] == ["ledger", "record"]
    # Descendants inherit the runner's publisher group and supervisor containment.
    child = subprocess.Popen([bun, orch, *arguments], stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = child.communicate(timeout=10)
    except BaseException:
        child.kill()
        child.communicate(timeout=3)
        raise
    entry = {"argv": [bun, orch, *arguments], "native_pid": child.pid,
             "native_exit": child.returncode, "native_stdout": stdout.decode(errors="replace"),
             "native_stderr": stderr.decode(errors="replace"), "record": is_record,
             "acknowledgment_withheld": is_record and child.returncode == 0}
    with Path(audit).open("a") as output:
        output.write(json.dumps(entry, sort_keys=True) + "\n")
        output.flush()
        os.fsync(output.fileno())
    if entry["acknowledgment_withheld"]:
        return 75
    sys.stdout.buffer.write(stdout)
    sys.stderr.buffer.write(stderr)
    return child.returncode


if __name__ == "__main__":
    raise SystemExit(main())
