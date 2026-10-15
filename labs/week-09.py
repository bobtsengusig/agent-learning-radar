"""Authorization contract exercise; this is not an MCP protocol implementation."""
import json

DOCUMENTS = {"public-guide": "Checkpoint saves task state.", "private-notes": "Private research"}
GRANTS = {"alice": {"public-guide"}, "bob": {"public-guide", "private-notes"}}
TOOL = {"name": "read_document", "inputSchema": {"type": "object",
        "properties": {"document_id": {"type": "string"}},
        "required": ["document_id"], "additionalProperties": False}}


def call_tool(principal, arguments):
    # principal must come from the authenticated transport, never from tool arguments.
    if set(arguments) != {"document_id"} or not isinstance(arguments["document_id"], str):
        return {"isError": True, "code": "invalid_arguments"}
    doc_id = arguments["document_id"]
    if doc_id not in GRANTS.get(principal, set()):
        return {"isError": True, "code": "forbidden"}
    return {"isError": False, "text": DOCUMENTS[doc_id]}


def run_demo():
    allowed = call_tool("alice", {"document_id": "public-guide"})
    denied = call_tool("alice", {"document_id": "private-notes"})
    forged = call_tool("alice", {"document_id": "private-notes", "principal": "bob"})
    assert not allowed["isError"] and denied["code"] == "forbidden"
    assert forged["code"] == "invalid_arguments"
    return {"tool_contract": TOOL, "allowed": allowed, "denied": denied, "forged_identity": forged,
            "scope": "tool policy only; MCP transport and authentication are separate"}


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
