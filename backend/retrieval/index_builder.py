import faiss
import pickle
from pathlib import Path
from typing import List, Tuple
from .data_loader import Chunk
from .embedder import embed_chunks
from app.config import settings

FAISS_PATH = settings.FAISS_PATH
ID_MAP_PATH = settings.ID_MAP_PATH


def build_faiss_index(
    chunks: List[Chunk],
    faiss_path: str = FAISS_PATH,
    id_map_path: str = ID_MAP_PATH,
) -> Tuple[faiss.Index, List[str]]:
    """
    Builds a FAISS index from chunk embeddings.
    Saves index and chunk_id map to disk.
    """
    faiss_file = Path(faiss_path)
    idmap_file = Path(id_map_path)

    if faiss_file.exists() and idmap_file.exists():
        print("âœ… FAISS index already exists â€” loading from disk...")
        return load_faiss_index(faiss_path, id_map_path)

    print("â³ Building FAISS index...")
    payload = embed_chunks(chunks)
    embeddings = payload["embeddings"]
    chunk_ids = payload["chunk_ids"]

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    faiss.write_index(index, faiss_path)
    with open(id_map_path, "wb") as f:
        pickle.dump(chunk_ids, f)

    print(f"âœ… FAISS index built with {index.ntotal} vectors")
    print(f"âœ… Index saved to {faiss_path}")
    print(f"âœ… ID map saved to {id_map_path}")
    return index, chunk_ids


def load_faiss_index(
    faiss_path: str = FAISS_PATH,
    id_map_path: str = ID_MAP_PATH,
) -> Tuple[faiss.Index, List[str]]:
    """
    Loads the saved FAISS index and chunk_id map from disk.
    """
    index = faiss.read_index(faiss_path)
    with open(id_map_path, "rb") as f:
        chunk_ids = pickle.load(f)
    print(f"âœ… FAISS index loaded â€” {index.ntotal} vectors ready")
    return index, chunk_ids
