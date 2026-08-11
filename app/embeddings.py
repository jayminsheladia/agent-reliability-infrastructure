EMBEDDING_DIM = 384

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> list[float]:
    """Local, no-API embedding — good enough to rank a handful of prior
    step outputs by relevance for this demo-scale retrieval problem."""
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Dot product is sufficient since embed_text() returns unit-normalized
    vectors — no need for a numpy dependency at this scale."""
    return sum(x * y for x, y in zip(a, b))
