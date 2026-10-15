"""Week 05: lexical vectors and Recall@k. These are NOT semantic embeddings."""
from collections import Counter
import json
import math
import re

DOCS = {
    "d1": "MCP connects agent tools and external data",
    "d2": "RAG retrieves document evidence before answering",
    "d3": "checkpoints persist workflow state for recovery",
    "d4": "evaluation measures agent task success and citations",
}


def tokens(text):
    return re.findall(r"[a-z]+", text.lower())


def vector(text):
    return Counter(tokens(text))


def cosine(a, b):
    dot = sum(value * b.get(key, 0) for key, value in a.items())
    norm = math.sqrt(sum(x*x for x in a.values()) * sum(x*x for x in b.values()))
    return dot / norm if norm else 0.0


def search(query, k=2):
    ranked = [(doc_id, cosine(vector(query), vector(text))) for doc_id, text in DOCS.items()]
    return sorted(ranked, key=lambda pair: (-pair[1], pair[0]))[:k]


def run_demo():
    cases = [("agent tools external data", {"d1"}), ("workflow recovery", {"d3"}), ("document evidence", {"d2"})]
    rows = []
    for query, relevant in cases:
        found = search(query, k=2)
        recall = len({key for key, score in found} & relevant) / len(relevant)
        rows.append({"query": query, "results": found, "recall_at_2": recall})
    assert all(row["recall_at_2"] == 1 for row in rows)
    return {"representation": "bag-of-words frequency vectors", "cases": rows,
            "synonym_test": search("remember progress after crash", 2),
            "note": "Try synonyms to observe lexical search limitations; then compare real embeddings."}


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
