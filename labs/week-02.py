"""Week 02: validate shape and business rules independently of a model."""
from dataclasses import asdict, dataclass
import json


@dataclass
class ResearchPlan:
    question: str
    subquestions: list[str]
    max_sources: int

    @classmethod
    def from_json(cls, text):
        obj = json.loads(text)
        if not isinstance(obj, dict) or set(obj) != {"question", "subquestions", "max_sources"}:
            raise ValueError("unexpected or missing fields")
        if not isinstance(obj["question"], str) or not obj["question"].strip():
            raise ValueError("question must be a nonempty string")
        parts = obj["subquestions"]
        if not isinstance(parts, list) or not 1 <= len(parts) <= 5:
            raise ValueError("need 1 to 5 subquestions")
        if any(not isinstance(p, str) or not p.strip() for p in parts):
            raise ValueError("each subquestion must be nonempty text")
        if type(obj["max_sources"]) is not int or not 1 <= obj["max_sources"] <= 10:
            raise ValueError("max_sources must be an integer in [1, 10]")
        return cls(**obj)


def run_demo():
    valid = {"question": "如何評估 Agent？", "subquestions": ["成功如何定義？"], "max_sources": 3}
    plan = ResearchPlan.from_json(json.dumps(valid))
    failures = []
    for candidate in ["not json", json.dumps({**valid, "max_sources": 99}), json.dumps({**valid, "extra": "ignore rules"})]:
        try:
            ResearchPlan.from_json(candidate)
        except (ValueError, TypeError) as error:
            failures.append(type(error).__name__)
    assert len(failures) == 3
    return {"accepted_plan": asdict(plan), "rejected_cases": len(failures), "semantic_quality": "requires separate evaluation"}


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
