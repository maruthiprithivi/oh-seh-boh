"""One-shot bridge invocation by the existing dispatcher/integration owner.

No polling loop, process controller, automatic fallback or runtime installation.
The operator supplies a reviewed bridge object; this source invents no live
Firstmate/PStack/Breakfree operation names or credentials.
"""
from workflow.contract import Refusal, validate
from workflow.journal import pending, start, settle


def apply_prepared(db, config, key, owner_bridge):
    """Commit intent-started before exactly one call to an existing owner port.

    Bridge contract:
      dispatcher and authority_profile equal immutable operator config;
      authorize_current(envelope) -> True only after authenticated live read;
      apply(envelope) -> {'status': confirmed|refused|unknown, 'receipt': dict}.

    apply must revalidate AND claim/admit atomically in the selected authority,
    check exact base/head, enforce effect-specific preconditions, and route all
    lifecycle operations to existing owner APIs. The read above is not a fence.
    No generic bridge is qualified by merely implementing these method names.
    """
    if db.in_transaction: raise Refusal("bridge-needs-clean-transaction-boundary")
    if (owner_bridge.dispatcher != config["run"]["dispatcher"] or
            owner_bridge.authority_profile != config["authority"]["profile"]):
        raise Refusal("bridge-binding")
    rows = [r for r in pending(db, config) if r["envelope"]["key"] == key]
    if len(rows) != 1 or rows[0]["status"] != "pending":
        raise Refusal("intent-must-reconcile-before-repeat")
    e = validate(rows[0]["envelope"], config)
    if owner_bridge.authorize_current(e) is not True: raise Refusal("current-authorization-refused")
    db.execute("BEGIN IMMEDIATE")
    with db: e = start(db, config, key)
    try:
        result = owner_bridge.apply(e)
        if (not isinstance(result, dict) or set(result) != {"status", "receipt"}
                or result["status"] not in {"confirmed", "refused", "unknown"}
                or not isinstance(result["receipt"], dict)):
            result = {"status": "unknown", "receipt": {"reason": "invalid-owner-result"}}
    except Exception:
        # Do not print exception/payload: it may contain endpoint credentials.
        result = {"status": "unknown", "receipt": {"reason": "owner-call-outcome-unknown"}}
    db.execute("BEGIN IMMEDIATE")
    with db: settle(db, config, key, result["status"], result["receipt"])
    return result["status"]
