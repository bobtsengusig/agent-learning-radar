"""Simulate replay after a crash using a durable-effect ledger abstraction."""
import json


def advance(state, approval, ledger, crash=False):
    if state["stage"] == "draft":
        state["stage"] = "awaiting_approval"
        return "paused"
    if state["stage"] == "awaiting_approval":
        if approval is None:
            return "paused"
        if not approval:
            state["stage"] = "rejected"
            return "rejected"
        # A stable operation ID is reused on retry. Real services must enforce it atomically.
        key = state["task_id"] + ":publish:v1"
        ledger.setdefault(key, "report-001")
        if crash:
            raise RuntimeError("crash after effect, before checkpoint")
        state["report_id"] = ledger[key]
        state["stage"] = "completed"
    return state["stage"]


def run_demo():
    state = {"task_id": "research-1", "stage": "draft"}
    ledger = {}
    assert advance(state, None, ledger) == "paused" and not ledger
    try:
        advance(state, True, ledger, crash=True)
    except RuntimeError:
        pass
    assert state["stage"] == "awaiting_approval" and len(ledger) == 1
    assert advance(state, True, ledger) == "completed" and len(ledger) == 1
    denied = {"task_id": "research-2", "stage": "awaiting_approval"}
    assert advance(denied, False, ledger) == "rejected" and len(ledger) == 1
    return {"recovered_task": state, "effect_count": len(ledger), "rejected_task": denied,
            "scope": "in-memory replay simulation; not crash-safe storage"}


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
