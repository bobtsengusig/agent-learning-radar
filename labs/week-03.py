"""Week 03: a bounded agent loop with a scripted model and an allowlisted tool."""
import json

DOCUMENTS = {"mcp": {"id": "doc-mcp", "text": "MCP connects applications with tools and data."}}


def search_docs(query):
    if not isinstance(query, str) or not 1 <= len(query) <= 80:
        raise ValueError("query must contain 1 to 80 characters")
    return [doc for key, doc in DOCUMENTS.items() if key in query.lower()]


def scripted_model(history):
    if not any(row["kind"] == "tool_result" for row in history):
        return {"kind": "tool_call", "name": "search_docs", "args": {"query": "mcp"}}
    evidence = history[-1]["result"]
    return {"kind": "final", "text": "找到 MCP 的工具與資料整合說明。", "citations": [x["id"] for x in evidence]}


def run_agent(question="MCP 是什麼？", decide=scripted_model, max_steps=4):
    tools = {"search_docs": search_docs}
    history = [{"kind": "user", "text": question}]
    for step in range(max_steps):
        action = decide(history)
        history.append({"step": step, **action})
        if action.get("kind") == "final":
            return {"status": "completed", "answer": action, "trace": history}
        name, args = action.get("name"), action.get("args")
        if name not in tools or not isinstance(args, dict) or set(args) != {"query"}:
            return {"status": "blocked", "reason": "unknown tool or invalid arguments", "trace": history}
        try:
            result = tools[name](**args)
        except (ValueError, TimeoutError) as error:
            return {"status": "failed", "reason": str(error), "trace": history}
        history.append({"kind": "tool_result", "name": name, "result": result})
    return {"status": "budget_exhausted", "trace": history}


def run_demo():
    normal = run_agent()
    blocked = run_agent(decide=lambda _: {"kind": "tool_call", "name": "delete_everything", "args": {}})
    looping = run_agent(decide=lambda _: {"kind": "tool_call", "name": "search_docs", "args": {"query": "mcp"}})
    assert (normal["status"], blocked["status"], looping["status"]) == ("completed", "blocked", "budget_exhausted")
    return {"normal": normal, "blocked": blocked["status"], "looping": looping["status"]}


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
