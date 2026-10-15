"""Week 04: fixed evaluation cases. No SDK or model service is called."""
import json


def baseline(question):
    return {"tool": "search_docs", "query": question}


def routed(question):
    if not question.strip():
        return {"tool": "clarify", "query": "請提供研究問題"}
    if len(question) > 80:
        return {"tool": "clarify", "query": "請縮小問題範圍"}
    return {"tool": "search_docs", "query": question}


def evaluate(system, cases):
    rows = []
    for case in cases:
        result = system(case["question"])
        passed = result["tool"] == case["expected_tool"] and bool(result["query"].strip())
        rows.append({"id": case["id"], "passed": passed, "actual_tool": result["tool"]})
    return {"passed": sum(r["passed"] for r in rows), "total": len(rows), "failures": [r for r in rows if not r["passed"]]}


def run_demo():
    cases = [{"id": f"normal-{n}", "question": f"research agent topic {n}", "expected_tool": "search_docs"} for n in range(16)]
    cases += [{"id": f"empty-{n}", "question": " " * n, "expected_tool": "clarify"} for n in range(4)]
    before, after = evaluate(baseline, cases), evaluate(routed, cases)
    assert before["passed"] == 16 and after["passed"] == 20
    return {"dataset_version": "routing-v1", "before": before, "after": after,
            "limit": "These deterministic cases measure routing contracts, not real LLM reasoning."}


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
