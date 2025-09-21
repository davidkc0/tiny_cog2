import os, math
from typing import List

# Try sentence-transformers first
try:
    from sentence_transformers import SentenceTransformer
    _MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
    _st = SentenceTransformer(_MODEL)

    def embed_texts(texts: List[str]) -> List[List[float]]:
        return _st.encode(texts, normalize_embeddings=True).tolist()

    def embed_text(text: str) -> List[float]:
        return embed_texts([text])[0]

except Exception:
    # Fallback: normalized BoW using a tiny local vocab
    def _tokenize(text: str):
        return [t.lower() for t in ''.join(ch if ch.isalnum() else ' ' for ch in text).split()]

    _VOCAB = {}

    def _bow(text: str):
        vec = [0.0] * len(_VOCAB)
        for t in _tokenize(text):
            if t not in _VOCAB:
                _VOCAB[t] = len(_VOCAB)
                vec.append(0.0)  # expand vector for new term
            idx = _VOCAB[t]
            # ensure vec is large enough (if vocab grew mid-loop)
            if idx >= len(vec):
                vec.extend([0.0] * (idx - len(vec) + 1))
            vec[idx] += 1.0
        n = math.sqrt(sum(v*v for v in vec)) or 1.0
        return [v/n for v in vec]

    def embed_texts(texts: List[str]) -> List[List[float]]:
        # Recompute each independently so dimension matches global vocab
        return [_bow(t) for t in texts]

    def embed_text(text: str) -> List[float]:
        return _bow(text)