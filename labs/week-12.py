"""Task lifecycle exercise. No server starts and no background process remains."""
import json


class TaskService:
    def __init__(self):
        self.tasks = {}
        self.keys = {}

    def create(self, key, question):
        if not question.strip():
            raise ValueError("question is required")
        if key in self.keys:
            task = self.tasks[self.keys[key]]
            if task["question"] != question:
                raise ValueError("idempotency key reused with different input")
            return task["id"]
        task_id = "task-" + str(len(self.tasks) + 1)
        self.tasks[task_id] = {"id": task_id, "question": question, "status": "queued", "report": None}
        self.keys[key] = task_id
        return task_id

    def cancel(self, task_id):
        task = self.tasks[task_id]
        if task["status"] in {"queued", "running"}:
            task["status"] = "cancelled"

    def step(self, task_id, deadline_exceeded=False):
        task = self.tasks[task_id]
        if task["status"] in {"completed", "cancelled", "timed_out"}:
            return
        if deadline_exceeded:
            task["status"] = "timed_out"
        elif task["status"] == "queued":
            task["status"] = "running"
        else:
            task.update(status="completed", report={"text": "離線示範報告", "evidence_ids": ["doc-1"]})


def run_demo():
    service = TaskService()
    first = service.create("request-1", "研究 checkpoint")
    assert first == service.create("request-1", "研究 checkpoint")
    service.step(first)
    service.step(first)
    cancelled = service.create("request-2", "研究 MCP")
    service.cancel(cancelled)
    service.step(cancelled)
    late = service.create("request-3", "研究 A2A")
    service.step(late, deadline_exceeded=True)
    assert [t["status"] for t in service.tasks.values()] == ["completed", "cancelled", "timed_out"]
    assert service.tasks[cancelled]["report"] is None
    return {"tasks": list(service.tasks.values()),
            "scope": "in-memory state machine; production needs durable storage, queue, authentication and monitoring"}


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
