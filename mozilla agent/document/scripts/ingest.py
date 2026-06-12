"""
Ingest documents into a local vector store using encoderfile for embeddings.

Usage:
    uv run python scripts/ingest.py --corpus-dir corpus/sample --encoderfile-url http://localhost:8085

This script:
1. Reads all .md and .txt files from the corpus directory
2. Chunks them into overlapping segments
3. Embeds each chunk via the encoderfile REST API
4. Saves the vector store to ./vector_store.json
"""

import argparse
import json
import os
from pathlib import Path

import numpy as np
import requests


def read_documents(corpus_dir: str) -> list[dict]:
    """Read all markdown and text files from a directory."""
    docs = []
    corpus_path = Path(corpus_dir)

    for ext in ("*.md", "*.txt"):
        for filepath in sorted(corpus_path.rglob(ext)):
            content = filepath.read_text(encoding="utf-8")
            docs.append(
                {
                    "path": str(filepath),
                    "filename": filepath.name,
                    "content": content,
                }
            )

    print(f"Read {len(docs)} documents from {corpus_dir}")
    return docs


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
) -> list[str]:
    """Split text into overlapping chunks by character count.

    Uses a simple character-based chunking strategy. For a hackathon
    this is fine — production systems would use sentence-aware splitting.
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Don't create tiny trailing chunks
        if len(chunk.strip()) < 50 and chunks:
            # Append to previous chunk instead
            chunks[-1] += chunk
        else:
            chunks.append(chunk.strip())

        start += chunk_size - overlap

    return [c for c in chunks if c]


def embed_texts(texts: list[str], encoderfile_url: str) -> list[list[float]]:
    """Embed a batch of texts using the encoderfile REST API."""
    response = requests.post(
        f"{encoderfile_url}/predict",
        json={"inputs": texts, "normalize": True},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    # encoderfile returns embeddings in the "results" field
    # Each result has an "embeddings" or the raw vector depending on model type
    results = data.get("results", data)

    embeddings = []
    for result in results:
        if isinstance(result, dict):
            token_embs = result.get("embeddings", result.get("logits", []))
            if token_embs and isinstance(token_embs[0], dict):
                # API returns per-token embeddings; mean-pool to get sentence vector
                vecs = np.array([t["embedding"] for t in token_embs], dtype=np.float32)
                emb = vecs.mean(axis=0).tolist()
            else:
                emb = token_embs
            embeddings.append(emb)
        elif isinstance(result, list):
            embeddings.append(result)

    return embeddings


def ingest(corpus_dir: str, encoderfile_url: str, output_path: str) -> None:
    """Main ingestion pipeline."""
    # 1. Read documents
    docs = read_documents(corpus_dir)
    if not docs:
        print(f"No .md or .txt files found in {corpus_dir}")
        return

    # 2. Chunk documents
    chunks = []
    for doc in docs:
        doc_chunks = chunk_text(doc["content"])
        for i, chunk_text_content in enumerate(doc_chunks):
            chunks.append(
                {
                    "id": f"{doc['filename']}:chunk_{i}",
                    "source": doc["filename"],
                    "path": doc["path"],
                    "text": chunk_text_content,
                }
            )

    print(f"Created {len(chunks)} chunks from {len(docs)} documents")

    # 3. Embed chunks (batch for efficiency)
    print(f"Embedding chunks via {encoderfile_url}...")
    batch_size = 32
    all_embeddings = []

    for i in range(0, len(chunks), batch_size):
        batch_texts = [c["text"] for c in chunks[i : i + batch_size]]
        batch_embeddings = embed_texts(batch_texts, encoderfile_url)
        all_embeddings.extend(batch_embeddings)
        print(f"  Embedded {min(i + batch_size, len(chunks))}/{len(chunks)} chunks")

    # 4. Save vector store
    vector_store = {
        "chunks": chunks,
        "embeddings": all_embeddings,
        "metadata": {
            "corpus_dir": corpus_dir,
            "num_documents": len(docs),
            "num_chunks": len(chunks),
            "embedding_dim": len(all_embeddings[0]) if all_embeddings else 0,
        },
    }

    with open(output_path, "w") as f:
        json.dump(vector_store, f)

    print(f"Vector store saved to {output_path}")
    print(f"  {vector_store['metadata']['num_documents']} documents")
    print(f"  {vector_store['metadata']['num_chunks']} chunks")
    print(f"  {vector_store['metadata']['embedding_dim']}-dimensional embeddings")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents into vector store")
    parser.add_argument(
        "--corpus-dir",
        default="corpus/sample",
        help="Directory containing .md/.txt files",
    )
    parser.add_argument(
        "--encoderfile-url",
        default="http://localhost:8085",
        help="URL of the running encoderfile server",
    )
    parser.add_argument(
        "--output",
        default="./vector_store.json",
        help="Path to save the vector store",
    )
    args = parser.parse_args()
    ingest(args.corpus_dir, args.encoderfile_url, args.output)
