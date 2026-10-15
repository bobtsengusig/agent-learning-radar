"""Week 01: a measured model interface. Offline simulation, not a real LLM."""
from dataclasses import asdict, dataclass
import json
from time import perf_counter


@dataclass
class ModelResult:
    text: str
    model: str
    input_chars: int
    output_chars: int


class MockModel:
    def generate(self, question):
        if not question.strip():
            raise ValueError("question must not be blank")
        answer = "先搜尋來源，再核對證據，最後產生附引用的報告。"
        # Character counts are NOT token counts. Real usage comes from the API.
        return ModelResult(answer, "offline-mock", len(question), len(answer))


def measure(model, questions):
    records = []
    for number, question in enumerate(questions, 1):
        start = perf_counter()
        row = {"case": number, "status": "ok"}
        try:
            row.update(asdict(model.generate(question)))
        except ValueError as error:
            row.update(status="error", error=str(error))
        row["latency_ms"] = round((perf_counter() - start) * 1000, 3)
        records.append(row)
    return records


def run_demo():
    rows = measure(MockModel(), ["如何設計研究助理？", "", "如何保存研究來源？"])
    assert all(r["status"] in {"ok", "error"} for r in rows)
    assert all(r["latency_ms"] >= 0 for r in rows)
    success_rate = sum(r["status"] == "ok" for r in rows) / len(rows) if rows else 0
    return {"mode": "offline simulation", "records": rows, "success_rate": success_rate}


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
