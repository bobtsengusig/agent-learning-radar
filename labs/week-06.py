"""Week 06: citation existence and exact-quote checks, not semantic entailment."""
import json

EVIDENCE = {
    "d1": "MCP provides a standard interface for tools and data.",
    "d2": "A checkpoint stores workflow state so execution can resume.",
}


def validate_report(report):
    errors = []
    for index, claim in enumerate(report["claims"]):
        evidence_id = claim["evidence_id"]
        if evidence_id not in EVIDENCE:
            errors.append(f"claim {index}: unknown source")
            continue
        if not claim["quote"] or claim["quote"] not in EVIDENCE[evidence_id]:
            errors.append(f"claim {index}: quote is not in source")
    return errors


def answer(topic):
    if topic == "checkpoint":
        return {"status": "supported", "claims": [{"text": "Checkpoint 可保存流程狀態。", "evidence_id": "d2", "quote": "A checkpoint stores workflow state"}]}
    return {"status": "insufficient_evidence", "claims": []}


def run_demo():
    supported = answer("checkpoint")
    invented = {"claims": [{"text": "保證零失敗", "evidence_id": "fake", "quote": "zero failures"}]}
    misleading = {"claims": [{"text": "MCP 保證任何工具都安全。", "evidence_id": "d1", "quote": "standard interface"}]}
    assert validate_report(supported) == []
    assert len(validate_report(invented)) == 1
    assert answer("unseen topic")["status"] == "insufficient_evidence"
    # This passes mechanical checks but is semantically unsupported: human review is still needed.
    assert validate_report(misleading) == []
    return {"supported": supported, "invented_errors": validate_report(invented),
            "unanswerable": answer("unseen topic"), "mechanical_check_blind_spot": misleading}


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
