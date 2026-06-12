from retrieval import search
import requests
from ddgs import DDGS   # FIXED IMPORT (IMPORTANT)


# -----------------------------
# WEB SEARCH TOOL (ROBUST + CLEAN)
# -----------------------------
def search_web(query):
    try:
        results = []

        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                title = r.get("title", "")
                body = r.get("body", "")

                if body:
                    results.append(f"{title}\n{body}")

        if not results:
            return None

        return "\n\n".join(results)

    except Exception as e:
        print("[WEB ERROR]", e)
        return None


# -----------------------------
# LOCAL DOC TOOL
# -----------------------------
def search_local_docs(query, k=3):
    results = search(query, k=k)

    if not results:
        return None

    # basic cleanup (prevents garbage chunks)
    filtered = [
        r for r in results
        if r and len(r.strip()) > 40
        and "MCPD Agent Ready" not in r
        and "Initializing Retrieval" not in r
    ]

    if not filtered:
        return None

    return "\n\n".join(filtered)


# -----------------------------
# LLM TOOL (LLAMAFILE SAFE MODE)
# -----------------------------
def ask_llm(prompt):
    url = "http://localhost:8080/v1/chat/completions"

    payload = {
        "model": "qwen",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a STRICT grounded assistant. "
                    "Only use provided context. Do not hallucinate."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2
    }

    try:
        r = requests.post(url, json=payload, timeout=60)
        data = r.json()

        return data["choices"][0]["message"]["content"]

    except Exception as e:
        return f"LLM error: {str(e)}"


# -----------------------------
# FALLBACK TOOL
# -----------------------------
def fallback_answer(query):
    return (
        "No reliable information found from local documents or web search.\n\n"
        f"Query: {query}\n"
        "Try rephrasing or adding more details."
    )