import numpy as np
import pickle
from pathlib import Path
from typing import List
from fastembed import TextEmbedding
from .data_loader import Chunk
from app.config import settings

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CACHE_PATH = settings.EMBEDDINGS_CACHE


def embed_chunks(chunks: List[Chunk], cache_path: str = CACHE_PATH) -> dict:
    """
    Converts each chunk's text into a 384-dimensional vector.
    Saves results to disk — won't re-embed if cache already exists.
    """
    cache = Path(cache_path)

    if cache.exists():
        print("✅ Loading cached embeddings from disk...")
        with open(cache, "rb") as f:
            return pickle.load(f)

    print(f"⏳ Embedding {len(chunks)} chunks via fastembed/ONNX (one-time, ~1 min)...")
    import os
    import tempfile
    cache_dir = os.environ.get("FASTEMBED_CACHE_PATH")
    if not cache_dir:
        if os.environ.get("VERCEL"):
            cache_dir = "/tmp/fastembed"
        else:
            cache_dir = os.path.join(tempfile.gettempdir(), "fastembed")
    os.makedirs(cache_dir, exist_ok=True)
    model = TextEmbedding(model_name=EMBED_MODEL, cache_dir=cache_dir)
    texts = [c.text for c in chunks]

    embeddings = np.array(
        list(model.embed(texts)), dtype=np.float32
    )  # shape: (n_chunks, 384)

    payload = {
        "embeddings": embeddings,
        "chunk_ids": [c.chunk_id for c in chunks],
    }

    with open(cache, "wb") as f:
        pickle.dump(payload, f)

    print(f"✅ Embeddings saved to {cache_path}")
    print(f"✅ Shape: {embeddings.shape}")
    return payload