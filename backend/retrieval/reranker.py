from typing import List, Dict, Any
from app.config import settings


def rerank_and_format(
    results: List[Dict[str, Any]],
    top_k: int = settings.DEFAULT_TOP_K,
    diversity_per_doc: int = settings.DIVERSITY_PER_DOC,
) -> List[Dict[str, Any]]:
    """
    Post-processes retrieval results:
    1. Diversity filter — caps chunks per document
    2. Confidence label — HIGH / MEDIUM / LOW
    3. Source label — human readable provenance
    """

    # ── 1. DIVERSITY FILTER ────────────────────────────────────────────────
    doc_counts: Dict[str, int] = {}
    filtered = []

    for r in results:
        doc_id = r["doc_id"]
        count = doc_counts.get(doc_id, 0)
        if count < diversity_per_doc:
            doc_counts[doc_id] = count + 1
            filtered.append(r)
        if len(filtered) >= top_k:
            break

    # ── 2. CONFIDENCE LABEL ────────────────────────────────────────────────
    for r in filtered:
        score = r["fused_score"]
        if score >= settings.HIGH_CONFIDENCE_THRESHOLD:
            r["confidence"] = "HIGH"
        elif score >= settings.MEDIUM_CONFIDENCE_THRESHOLD:
            r["confidence"] = "MEDIUM"
        else:
            r["confidence"] = "LOW"

    # ── 3. SOURCE LABEL ────────────────────────────────────────────────────
    for r in filtered:
        r["source"] = (
            f"{r['doc_id']} · "
            f"pages {r['page_start']}–{r['page_end']}"
        )

    return filtered


def print_results(results: List[Dict[str, Any]]):
    """Prints results cleanly in the terminal for debugging."""
    if not results:
        print("⚠️  No results to display")
        return

    print(f"\n{'='*60}")
    print(f"  TOP {len(results)} RESULTS")
    print(f"{'='*60}")

    for i, r in enumerate(results, 1):
        print(f"\n[{i}] {r['confidence']} confidence — score: {r['fused_score']}")
        print(f"    Source   : {r['source']}")
        print(f"    Products : {r['product_names']}")
        print(f"    Standards: {r['standards'][:2]}")
        print(f"    Text     : {r['text'][:150]}...")
        print(f"    {'─'*50}")