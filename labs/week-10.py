"""Compare role separation on synthetic artifacts; no model is called."""
import json
import math


def percentile95(values):
    return sorted(values)[math.ceil(len(values) * .95) - 1]


def run_demo():
    cases = [{"id": i, "has_evidence": i % 4 != 0} for i in range(20)]
    single, split = [], []
    for case in cases:
        draft = {"claim": "checkpoint 可以保存狀態", "evidence_ids": ["doc-1"] if case["has_evidence"] else []}
        # A deterministic checker flags missing evidence; it cannot verify meaning.
        checked = dict(draft, status="answered" if draft["evidence_ids"] else "insufficient_evidence")
        single.append({"success": bool(draft["evidence_ids"]), "calls": 1, "simulated_ms": 100})
        split.append({"success": checked["status"] == ("answered" if case["has_evidence"] else "insufficient_evidence"),
                      "calls": 2, "simulated_ms": 180})

    def metrics(rows):
        return {"cases": len(rows), "contract_success": sum(r["success"] for r in rows) / len(rows),
                "calls": sum(r["calls"] for r in rows), "simulated_p95_ms": percentile95([r["simulated_ms"] for r in rows])}

    assert metrics(single)["contract_success"] == .75 and metrics(split)["contract_success"] == 1
    return {"single": metrics(single), "research_and_check": metrics(split),
            "warning": "synthetic numbers demonstrate accounting, not evidence that multi-agent is better"}


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
