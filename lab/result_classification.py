"""Classify supervisor observations, not logs or untrusted claimed CI status.

Synthetic fixture helper only; it does not verify a provider, test trace or digest.
"""


def classify(observation):
    state = "notexecuted"
    if observation.get("started") is True:
        if observation.get("setup_ok") is not True:
            state = "setupfailed"
        elif observation.get("cancelled") is True:
            state = "cancelled"
        elif observation.get("behavior_ok") is True:
            state = "pass"
        else:
            state = "behaviorfailure"
    proof = (state == "pass" and observation.get("compiled") is True
             and type(observation.get("test_exit")) is int
             and observation.get("test_exit") == 1
             and observation.get("expected_assertion_observed") is True)
    return {"state": state, "expected_red_proof": proof}
