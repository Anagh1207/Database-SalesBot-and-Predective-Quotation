from typing import List, Optional
from .retriever import retrieve
from .reranker import rerank_and_format, print_results
from app.config import settings


def search(
    query: str,
    top_k: int = settings.DEFAULT_TOP_K,
    doc_ids: List[str] = None,
    min_technicality: float = settings.DEFAULT_MIN_TECHNICALITY,
    standards_contain: str = None,
    show_results: bool = False,
) -> dict:
    """
    Single public function your chatbot calls.
    Returns a structured dict with ranked results.
    """
    raw = retrieve(
        query=query,
        top_k=top_k * 2,
        doc_ids=doc_ids,
        min_technicality=min_technicality,
        standards_contain=standards_contain,
    )

    results = rerank_and_format(raw, top_k=top_k)

    if show_results:
        print_results(results)

    return {
        "query": query,
        "total_raw": len(raw),
        "count": len(results),
        "results": results,
    }