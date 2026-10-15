"""Task-scoped memory with SQLite; the database is intentionally in memory."""
import json
import sqlite3


def run_demo():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE tasks (owner TEXT, task TEXT, body TEXT, PRIMARY KEY(owner, task))")
    for owner, task, question in [("alice", "r1", "研究 checkpoint"), ("bob", "r1", "研究 MCP")]:
        body = {"question": question, "constraints": ["必須附引用"], "evidence_ids": [], "notes": []}
        db.execute("INSERT INTO tasks VALUES (?, ?, ?)", (owner, task, json.dumps(body)))

    def load(owner, task):
        row = db.execute("SELECT body FROM tasks WHERE owner=? AND task=?", (owner, task)).fetchone()
        return json.loads(row[0]) if row else None

    alice = load("alice", "r1")
    alice["notes"] = ["已讀資料 " + str(i) for i in range(20)]
    # Select fields explicitly; never summarize away a hard constraint.
    context = {"question": alice["question"], "constraints": alice["constraints"],
               "evidence_ids": alice["evidence_ids"], "recent_notes": alice["notes"][-3:]}
    assert "必須附引用" in context["constraints"] and len(context["recent_notes"]) == 3
    assert load("bob", "r1")["question"] == "研究 MCP"
    assert load("mallory", "r1") is None
    db.execute("DELETE FROM tasks WHERE owner=? AND task=?", ("alice", "r1"))
    assert load("alice", "r1") is None and load("bob", "r1") is not None
    db.close()
    return {"context": context, "isolation_check": "passed", "deletion_check": "passed",
            "persistence": "demo uses :memory:; use a file path and commit for restart persistence"}


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
