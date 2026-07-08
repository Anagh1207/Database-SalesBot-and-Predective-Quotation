import json
import numpy as np
from typing import List, Dict, Any, Optional
from fastembed import TextEmbedding
from .metadata_store import filter_chunks
from .index_builder import load_faiss_index
from app.config import settings

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_model = None


def get_model():
    global _model
    if _model is None:
        print("[retriever] Loading embedding model (fastembed/ONNX)...")
        import os
        import tempfile
        # Check if we are running in Vercel or need a writable cache dir
        cache_dir = os.environ.get("FASTEMBED_CACHE_PATH")
        if not cache_dir:
            if os.environ.get("VERCEL"):
                cache_dir = "/tmp/fastembed"
            else:
                cache_dir = os.path.join(tempfile.gettempdir(), "fastembed")
        os.makedirs(cache_dir, exist_ok=True)
        _model = TextEmbedding(model_name=MODEL_NAME, cache_dir=cache_dir)
        print("[retriever] Model ready")
    return _model



def retrieve(
    query: str,
    top_k: int = settings.DEFAULT_TOP_K,
    doc_ids: List[str] = None,
    min_technicality: float = settings.DEFAULT_MIN_TECHNICALITY,
    standards_contain: str = None,
    vector_weight: float = settings.VECTOR_WEIGHT,
    metadata_boost_weight: float = settings.METADATA_BOOST_WEIGHT,
) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval:
    1. Pre-filter by metadata
    2. Embed the query
    3. FAISS vector search
    4. Intersect results
    5. Fuse scores and rank
    """

    # ── 1. METADATA PRE-FILTER ─────────────────────────────────────────────
    candidates = filter_chunks(
        doc_ids=doc_ids,
        min_technicality=min_technicality,
        standards_contain=standards_contain,
    )

    if not candidates:
        print("[retriever] No chunks passed the metadata filter")
        return []

    candidate_id_set = {row["chunk_id"] for row in candidates}
    candidate_map = {row["chunk_id"]: row for row in candidates}

    # ── 2. EMBED THE QUERY ─────────────────────────────────────────────────
    model = get_model()
    query_vec = np.array(
        list(model.embed([query])), dtype=np.float32
    )  # shape: (1, 384)

    # ── 3. FAISS VECTOR SEARCH ─────────────────────────────────────────────
    index, chunk_ids = load_faiss_index()
    search_k = min(index.ntotal, top_k * 5)
    scores, indices = index.search(query_vec, search_k)
    scores = scores[0]
    indices = indices[0]

    # ── 4. INTERSECT WITH METADATA CANDIDATES ──────────────────────────────
    vector_hits = []
    for rank, (score, idx) in enumerate(zip(scores, indices)):
        if idx == -1:
            continue
        cid = chunk_ids[idx]
        if cid in candidate_id_set:
            vector_hits.append({
                "chunk_id": cid,
                "vector_score": float(score),
                "faiss_rank": rank,
            })

    if not vector_hits:
        print("[retriever] No results after intersecting with metadata filter")
        return []

    # ── 5. SCORE FUSION ────────────────────────────────────────────────────
    results = []
    for hit in vector_hits:
        cid = hit["chunk_id"]
        row = candidate_map[cid]
        vector_score = hit["vector_score"]
        tech_score = float(row["technicality_score"])
        rrf_score = 1.0 / (60 + hit["faiss_rank"])
        fused_score = (
            (vector_weight * vector_score) +
            (metadata_boost_weight * tech_score) +
            rrf_score
        )
        results.append({
            "chunk_id": cid,
            "doc_id": row["doc_id"],
            "text": row["text"],
            "page_start": row["page_start"],
            "page_end": row["page_end"],
            "vector_score": round(vector_score, 4),
            "technicality_score": tech_score,
            "fused_score": round(fused_score, 4),
            "standards": json.loads(row["standards"] or "[]"),
            "product_names": json.loads(row["product_names"] or "[]"),
            "constraints": json.loads(row["constraints"] or "[]"),
            "functional_properties": json.loads(row["functional_properties"] or "[]"),
        })

    results.sort(key=lambda x: x["fused_score"], reverse=True)
    print(f"[retriever] Retrieved {len(results[:top_k])} results for query: '{query[:60]}'")
    return results[:top_k]