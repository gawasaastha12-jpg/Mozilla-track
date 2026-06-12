import os
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# -----------------------------
# Embedding Model
# -----------------------------
model = SentenceTransformer("all-MiniLM-L6-v2")


# -----------------------------
# Load Starter Kit Documents
# -----------------------------
def load_documents(base_folder="document"):
    docs = []

    if not os.path.exists(base_folder):
        raise FileNotFoundError(f"Folder '{base_folder}' not found")

    print(f"\n📂 Scanning starter kit: {base_folder}")

    for root, _, files in os.walk(base_folder):
        for file in files:

            # ✅ SUPPORT .txt + .md
            if file.endswith((".txt", ".md")):

                path = os.path.join(root, file)

                try:
                    with open(path, "r", encoding="utf-8") as f:
                        text = f.read().strip()

                        if text:
                            rel_path = os.path.relpath(path, base_folder)
                            docs.append((rel_path, text))

                except Exception as e:
                    print(f"⚠️ Error reading {path}: {e}")

    print(f"📄 TOTAL FILES LOADED: {len(docs)}")
    return docs


# -----------------------------
# Chunking (good for RAG)
# -----------------------------
def chunk_text(text, chunk_size=80, overlap=20):
    words = text.split()

    if not words:
        return []

    chunks = []
    i = 0

    while i < len(words):
        chunk = words[i:i + chunk_size]
        chunks.append(" ".join(chunk))
        i += (chunk_size - overlap)

    return chunks


# -----------------------------
# Vector Store (FAISS)
# -----------------------------
class VectorStore:
    def __init__(self):
        self.index = None
        self.chunks = []

    def build(self, docs):
        all_chunks = []

        print("\n🧩 Building chunks...")

        for name, text in docs:
            chunks = chunk_text(text)
            print(f"   ✔ {name}: {len(chunks)} chunks")
            all_chunks.extend(chunks)

        print(f"\n🧠 TOTAL CHUNKS: {len(all_chunks)}")

        # ❌ HARD STOP if no data
        if len(all_chunks) == 0:
            raise ValueError("No chunks created. Check document/corpus content.")

        self.chunks = all_chunks

        print("\n⚙️ Creating embeddings...")

        embeddings = model.encode(all_chunks)
        embeddings = np.array(embeddings, dtype="float32")

        # safety reshape
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        dim = embeddings.shape[1]

        # FAISS index
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(embeddings)

        print("✅ FAISS index ready")

    def search(self, query, k=3):
        if self.index is None:
            raise ValueError("Index not built. Run initialize() first.")

        query_vec = model.encode([query])
        query_vec = np.array(query_vec, dtype="float32")

        if query_vec.ndim == 1:
            query_vec = query_vec.reshape(1, -1)

        _, indices = self.index.search(query_vec, k)

        results = []
        for idx in indices[0]:
            if 0 <= idx < len(self.chunks):
                results.append(self.chunks[idx])

        return results


# -----------------------------
# Global store
# -----------------------------
store = VectorStore()


# -----------------------------
# Initialize pipeline
# -----------------------------
def initialize():
    docs = load_documents("document")
    store.build(docs)


# -----------------------------
# Public search API
# -----------------------------
def search(query, k=3):
    return store.search(query, k)