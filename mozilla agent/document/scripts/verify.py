"""
Verify the RAG pipeline works end-to-end.

Usage:
    uv run python scripts/verify.py "What is the retry policy?"

This script:
1. Embeds the query via encoderfile
2. Searches the local vector store
3. Sends the retrieved context + query to llamafile for generation
4. Prints the grounded answer

This does NOT use mcpd or tinyagent — it's a direct pipeline test
to confirm your models and vector store are working before you
build the agent.
"""

import argparse
import json
import sys

import numpy as np
import requests


def embed_query(query: str, encoderfile_url: str) -> np.ndarray:
    """Embed query via encoderfile."""
    response = requests.post(
        f"{encoderfile_url}/predict",
        json={"inputs": [query], "normalize": True},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    results = data.get("results", data)
    result = results[0]
    if isinstance(result, list):
        vec = result
    else:
        token_embs = result.get("embeddings", [])
        if token_embs and isinstance(token_embs[0], dict):
            # API returns per-token embeddings; mean-pool to get sentence vector
            vecs = np.array([t["embedding"] for t in token_embs], dtype=np.float32)
            vec = vecs.mean(axis=0)
        else:
            vec = token_embs
    return np.array(vec, dtype=np.float32)


def search_store(store: dict, query_vec: np.ndarray, top_k: int = 3) -> list[dict]:
    """Search vector store by cosine similarity."""
    embeddings = np.array(store["embeddings"], dtype=np.float32)
    similarities = embeddings @ query_vec
    top_indices = np.argsort(similarities)[::-1][:top_k]

    results = []
    for idx in top_indices:
        chunk = store["chunks"][idx]
        results.append(
            {
                "source": chunk["source"],
                "text": chunk["text"],
                "score": float(similarities[idx]),
            }
        )
    return results


def generate_answer(
    query: str, context_chunks: list[dict], llamafile_url: str
) -> str:
    """Generate an answer using llamafile with retrieved context."""
    context = "\n\n---\n\n".join(
        f"[From {c['source']}]:\n{c['text']}" for c in context_chunks
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant that answers questions based on "
                "the provided documentation. Always cite which document your "
                "answer comes from. If the documentation doesn't contain the "
                "answer, say so clearly."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Documentation context:\n\n{context}\n\n"
                f"Question: {query}\n\n"
                "Answer based on the documentation above:"
            ),
        },
    ]

    response = requests.post(
        f"{llamafile_url}/v1/chat/completions",
        json={
            "model": "local",
            "messages": messages,
            "max_tokens": 512,
            "temperature": 0.1,
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def main():
    parser = argparse.ArgumentParser(description="Verify RAG pipeline")
    parser.add_argument("query", help="Question to ask")
    parser.add_argument(
        "--encoderfile-url", default="http://localhost:8085"
    )
    parser.add_argument(
        "--llamafile-url", default="http://localhost:8086"
    )
    parser.add_argument(
        "--vector-store", default="./vector_store.json"
    )
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    # Load vector store
    print("Loading vector store...")
    with open(args.vector_store) as f:
        store = json.load(f)

    # Search
    print(f"Searching for: {args.query}")
    query_vec = embed_query(args.query, args.encoderfile_url)
    results = search_store(store, query_vec, args.top_k)

    print(f"\nRetrieved {len(results)} chunks:")
    for r in results:
        print(f"  [{r['score']:.3f}] {r['source']}: {r['text'][:80]}...")

    # Generate
    print("\nGenerating answer...")
    answer = generate_answer(args.query, results, args.llamafile_url)

    print("\n" + "=" * 60)
    print("ANSWER:")
    print("=" * 60)
    print(answer)


if __name__ == "__main__":
    main()
