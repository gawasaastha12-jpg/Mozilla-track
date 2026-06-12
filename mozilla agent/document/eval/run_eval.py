"""
Evaluation runner for Know Your Docs.

Usage:
    uv run python eval/run_eval.py
    uv run python eval/run_eval.py --questions eval/questions.yaml --verbose

This script:
1. Loads questions from a YAML file
2. Runs each question through your agent
3. Scores each answer on:
   - Routing correctness: did the agent use the right tool(s)?
   - Keyword presence: do expected keywords appear in the answer?
4. Prints a summary report

Note: This is a lightweight eval for a hackathon. For production,
use a more robust evaluation harness with traced tool calls.
"""

import argparse
import sys
from pathlib import Path

import yaml

from mcpd import McpdClient
from tinyagent import AgentConfig, TinyAgent


# Import agent config from main
sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))


def load_questions(path: str) -> list[dict]:
    """Load evaluation questions from YAML."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["questions"]


def score_answer(answer: str, question: dict) -> dict:
    """Score an answer against expected criteria."""
    answer_lower = answer.lower()

    # Keyword scoring
    expected_keywords = question.get("expected_keywords", [])
    keywords_found = []
    keywords_missing = []
    for kw in expected_keywords:
        if kw.lower() in answer_lower:
            keywords_found.append(kw)
        else:
            keywords_missing.append(kw)

    keyword_score = (
        len(keywords_found) / len(expected_keywords) if expected_keywords else 1.0
    )

    # Simple routing detection (check if tool names appear in trace/answer)
    # In a real eval you'd inspect the agent trace for tool calls
    used_local = any(
        term in answer_lower
        for term in ["local doc", "internal doc", "architecture", "runbook", "api-spec", "search_docs"]
    )
    used_external = any(
        term in answer_lower
        for term in [
            "stripe",
            "aws",
            "industry",
            "web",
            "external",
            "according to",
            "search_text",
            "extract_content",
            "ddgs",
        ]
    )

    category = question.get("category", "unknown")
    if category == "local_only":
        routing_correct = used_local or keyword_score > 0.5
    elif category == "external_only":
        routing_correct = used_external or keyword_score > 0.5
    elif category == "hybrid":
        routing_correct = (used_local and used_external) or keyword_score > 0.5
    elif category == "negative":
        routing_correct = any(
            phrase in answer_lower
            for phrase in ["don't know", "not found", "no information", "don't have", "not in"]
        )
    else:
        routing_correct = True

    return {
        "keyword_score": keyword_score,
        "keywords_found": keywords_found,
        "keywords_missing": keywords_missing,
        "routing_correct": routing_correct,
        "category": category,
    }


def run_eval(questions_path: str, verbose: bool = False) -> None:
    """Run the full evaluation."""
    questions = load_questions(questions_path)
    print(f"Loaded {len(questions)} evaluation questions\n")

    # Connect to mcpd
    client = McpdClient(api_endpoint="http://localhost:8090")
    tools = client.agent_tools()

    # Create agent (same config as agent/main.py)
    agent = TinyAgent.create(
        AgentConfig(
            model_id="openai/local",
            api_base="http://localhost:8086/v1",
            api_key="local",
            instructions=(
                "You are a helpful assistant with access to local documents "
                "and web search tools. Always cite your sources."
            ),
            tools=tools,
        ),
    )

    results = []
    for i, q in enumerate(questions):
        print(f"[{i + 1}/{len(questions)}] {q['query'][:60]}...")

        try:
            trace = agent.run(q["query"])
            answer = str(trace)
            scores = score_answer(answer, q)
            scores["query"] = q["query"]
            scores["answer"] = answer[:200] + "..." if len(answer) > 200 else answer
            scores["error"] = None
        except Exception as e:
            scores = {
                "query": q["query"],
                "answer": "",
                "keyword_score": 0.0,
                "keywords_found": [],
                "keywords_missing": q.get("expected_keywords", []),
                "routing_correct": False,
                "category": q.get("category", "unknown"),
                "error": str(e),
            }

        results.append(scores)

        if verbose:
            status = "✅" if scores["routing_correct"] else "❌"
            print(f"  {status} Keywords: {scores['keyword_score']:.0%} | "
                  f"Routing: {'correct' if scores['routing_correct'] else 'WRONG'}")
            if scores["error"]:
                print(f"  ⚠️  Error: {scores['error']}")

    # --- Summary Report ---
    print("\n" + "=" * 70)
    print("EVALUATION REPORT")
    print("=" * 70)

    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "routing_correct": 0, "keyword_scores": []}
        categories[cat]["total"] += 1
        if r["routing_correct"]:
            categories[cat]["routing_correct"] += 1
        categories[cat]["keyword_scores"].append(r["keyword_score"])

    for cat, stats in categories.items():
        routing_pct = stats["routing_correct"] / stats["total"] * 100
        avg_keyword = sum(stats["keyword_scores"]) / len(stats["keyword_scores"]) * 100
        print(f"\n  {cat.upper()} ({stats['total']} questions)")
        print(f"    Routing accuracy:  {routing_pct:.0f}%")
        print(f"    Keyword coverage:  {avg_keyword:.0f}%")

    # Overall
    total = len(results)
    total_routing = sum(1 for r in results if r["routing_correct"])
    total_keyword = sum(r["keyword_score"] for r in results) / total * 100
    errors = sum(1 for r in results if r["error"])

    print(f"\n  OVERALL ({total} questions)")
    print(f"    Routing accuracy:  {total_routing / total * 100:.0f}%")
    print(f"    Keyword coverage:  {total_keyword:.0f}%")
    if errors:
        print(f"    Errors:            {errors}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Run evaluation")
    parser.add_argument(
        "--questions",
        default="eval/questions.yaml",
        help="Path to questions YAML file",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-question results",
    )
    args = parser.parse_args()
    run_eval(args.questions, args.verbose)


if __name__ == "__main__":
    main()
