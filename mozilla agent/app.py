import os
from retrieval import initialize
from tools import search_local_docs, ask_llm, fallback_answer, search_web

os.environ["OPENAI_API_KEY"] = "dummy"
os.environ["OPENAI_BASE_URL"] = "http://localhost:8080"

print("\nInitializing Retrieval System...")
initialize()
print("Retrieval Ready\n")


# -----------------------------
# QUERY CLASSIFIER
# -----------------------------
def classify_query(query: str):
    q = query.lower()
    return {
        "time_sensitive": any(k in q for k in [
            "latest", "news", "2026", "today", "current", "trends"
        ]),
        "conceptual": any(k in q for k in [
            "why", "how", "explain", "compare", "tradeoff"
        ]),
        "doc_intent": any(k in q for k in [
            "runbook", "architecture", "api", "readme", "spec", "system",
            "summarize", "summary", "describe", "what is"
        ])
    }


# -----------------------------
# RELEVANCE SCORE  (FIX: score on CONTEXT words, not query words)
# -----------------------------
def relevance_score(query, context):
    if not context:
        return -99

    q_words = [w for w in query.lower().split() if len(w) > 3]  # skip short stop words
    c_text = context.lower()

    # Count how many meaningful query words appear in context
    hits = sum(1 for w in q_words if w in c_text)

    # Penalty only for truly irrelevant boilerplate
    junk = ["llamafile", "encoderfile", "initializing retrieval", "mcpd agent ready"]
    penalty = sum(2 for j in junk if j in c_text)

    score = hits - penalty
    print(f"[MCPD] LOCAL SCORE: {score}  (hits={hits}, penalty={penalty}, query_words={q_words})")
    return score


def is_good_local_context(query, context):
    if not context:
        return False
    score = relevance_score(query, context)
    # Accept if at least 1 meaningful query word found and no heavy penalties
    if score < 1:
        print("→ LOCAL DOCS REJECTED (low relevance)")
        return False
    return True


# -----------------------------
# LLM WITH GRACEFUL ERROR MSG
# -----------------------------
def ask_llm_safe(prompt):
    result = ask_llm(prompt)
    if result.startswith("LLM error:"):
        print(f"[MCPD] Local LLM failed: {result}")
        return "⚠️ Local LLM is unavailable (timeout or not running). Please make sure llamafile is started on port 8080."
    return result


# -----------------------------
# ROUTER
# -----------------------------
def route_query(query):
    print("\n MCPD Brain Mode Active...\n")
    meta = classify_query(query)
    print(f"[DEBUG] doc={meta['doc_intent']} time={meta['time_sensitive']} concept={meta['conceptual']}")

    # ── STEP 1: LOCAL DOCS ──────────────────────────────────────────
    context = search_local_docs(query)

    # doc_intent queries: trust FAISS retrieval directly, skip relevance gate
    use_local = (meta["doc_intent"] and bool(context)) or is_good_local_context(query, context)

    if use_local:
        print("→ TOOL: LOCAL DOCS")
        return ask_llm_safe(f"""
STRICT RULES:
- Answer ONLY from the context below.
- If the answer is not in the context, say "Not found in documents."

CONTEXT:
{context}

QUESTION:
{query}
""")

    # ── STEP 2: WEB SEARCH (time-sensitive OR doc intent failed) ────
    if meta["time_sensitive"] or meta["doc_intent"]:
        print("→ TOOL: WEB SEARCH")
        web_context = search_web(query)

        if web_context:
            return ask_llm_safe(f"""
Use ONLY the web search results below to answer.

WEB RESULTS:
{web_context}

QUESTION:
{query}
""")
        print("[MCPD] WEB SEARCH RETURNED NOTHING")

    # ── STEP 3: LLM REASONING (conceptual) ─────────────────────────
    if meta["conceptual"]:
        print("→ TOOL: LLM REASONING")
        return ask_llm_safe(f"Explain clearly and logically:\n\n{query}")

    # ── STEP 4: FALLBACK ────────────────────────────────────────────
    print("→ TOOL: FALLBACK")
    return fallback_answer(query)


# -----------------------------
# CLI LOOP
# -----------------------------
if __name__ == "__main__":
    print("MCPD Agent Ready (type 'exit')\n")

    while True:
        q = input("You: ").strip()
        if not q:
            continue
        if q.lower() == "exit":
            break

        print("\nThinking...\n")
        ans = route_query(q)
        print("\nAnswer:\n", ans)
        print("\n" + "-" * 60)