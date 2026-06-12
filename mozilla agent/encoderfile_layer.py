from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")


def encode(texts):
    """
    Encoderfile-style embedding interface (COMPLIANCE WRAPPER)
    """
    return model.encode(texts, normalize_embeddings=True)