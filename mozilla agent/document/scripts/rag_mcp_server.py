"""
RAG MCP Server — exposes local document search as an MCP tool.

This script runs as a stdio MCP server managed by mcpd. It loads the
vector store created by ingest.py and exposes a `search_docs` tool
that agents can call to search your private documents.

The search flow:
1. Receive a query from the agent via MCP
2. Embed the query using encoderfile
3. Cosine similarity search against the vector store
4. Return the top-k most relevant chunks

Usage (standalone for testing):
    uv run python scripts/rag_mcp_server.py

In production, mcpd manages this server via .mcpd.toml.

Environment variables:
    ENCODERFILE_URL  — URL of the encoderfile embedding server (default: http://localhost:8085)
    VECTOR_STORE     — Path to the vector store JSON file (default: ./vector_store.json)
    TOP_K            — Number of results to return (default: 5)
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import requests

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# --- Configuration ---
ENCODERFILE_URL = os.environ.get("ENCODERFILE_URL", "http://localhost:8085")
_SCRIPT_ROOT = Path(__file__).resolve().parent.parent
_CWD_STORE = Path.cwd() / "vector_store.json"
_SCRIPT_STORE = _SCRIPT_ROOT / "vector_store.json"
_DEFAULT_STORE = _CWD_STORE if _CWD_STORE.exists() else _SCRIPT_STORE
VECTOR_STORE_PATH = os.environ.get("VECTOR_STORE", str(_DEFAULT_STORE))
TOP_K = int(os.environ.get("TOP_K", "5"))


def load_vector_store(path: str) -> dict:
    """Load the vector store from disk."""
    with open(path) as f:
        store = json.load(f)

    # Convert embeddings to numpy for fast similarity search
    store["_embeddings_np"] = np.array(store["embeddings"], dtype=np.float32)
    return store


def embed_query(query: str) -> np.ndarray:
    """Embed a query string using the encoderfile REST API."""
    response = requests.post(
        f"{ENCODERFILE_URL}/predict",
        json={"inputs": [query], "normalize": True},
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    results = data.get("results", data)
    result = results[0]
    if isinstance(result, list):
        vec = result
    else:
        token_embs = result.get("embeddings", result.get("logits", []))
        if token_embs and isinstance(token_embs[0], dict):
            # API returns per-token embeddings; mean-pool to get sentence vector
            vecs = np.array([t["embedding"] for t in token_embs], dtype=np.float32)
            vec = vecs.mean(axis=0)
        else:
            vec = token_embs

    return np.array(vec, dtype=np.float32)


def search(store: dict, query: str, top_k: int = TOP_K) -> list[dict]:
    """Search the vector store for chunks similar to the query."""
    query_vec = embed_query(query)
    embeddings = store["_embeddings_np"]

    # Cosine similarity (vectors are already normalized)
    similarities = embeddings @ query_vec

    # Get top-k indices
    top_indices = np.argsort(similarities)[::-1][:top_k]

    results = []
    for idx in top_indices:
        chunk = store["chunks"][idx]
        results.append(
            {
                "source": chunk["source"],
                "chunk_id": chunk["id"],
                "text": chunk["text"],
                "score": float(similarities[idx]),
            }
        )

    return results


# --- MCP Server ---

app = Server("rag")

# Load vector store at startup
try:
    vector_store = load_vector_store(VECTOR_STORE_PATH)
    print(
        f"Loaded vector store: {vector_store['metadata']['num_chunks']} chunks",
        file=sys.stderr,
    )
except FileNotFoundError:
    print(
        f"WARNING: Vector store not found at {VECTOR_STORE_PATH}. "
        "Run scripts/ingest.py first.",
        file=sys.stderr,
    )
    vector_store = None


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_docs",
            description=(
                "Search through private local documents. Use this tool to find "
                "information in the user's internal documentation, architecture "
                "decisions, runbooks, API specs, and other private files. "
                "Returns the most relevant text chunks with source attribution."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query",
                    },
                },
                "required": ["query"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name != "search_docs":
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    if vector_store is None:
        return [
            TextContent(
                type="text",
                text="Error: Vector store not loaded. Run scripts/ingest.py first.",
            )
        ]

    query = arguments.get("query", "")
    if not query:
        return [TextContent(type="text", text="Error: 'query' parameter is required.")]

    results = search(vector_store, query)

    # Format results for the agent
    formatted = []
    for r in results:
        formatted.append(
            f"[Source: {r['source']} | Score: {r['score']:.3f}]\n{r['text']}"
        )

    output = f"Found {len(results)} relevant chunks:\n\n" + "\n\n---\n\n".join(
        formatted
    )

    return [TextContent(type="text", text=output)]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def sync_main():
    import asyncio
    asyncio.run(main())


if __name__ == "__main__":
    sync_main()
