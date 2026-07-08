from fastapi import APIRouter, HTTPException
from app.models import SearchRequest, SearchResponse
from retrieval.search import search
from app.logger import get_logger
import time

router = APIRouter(
    prefix="/search",
    tags=["Search"],
)

logger = get_logger("search")


@router.post("", response_model=SearchResponse)
def run_search(request: SearchRequest):
    """
    Main search endpoint.
    Returns ranked chunks with confidence scores.
    """
    start = time.time()
    logger.info(f"Search query: '{request.query}' | top_k={request.top_k}")

    try:
        response = search(
            query=request.query,
            top_k=request.top_k,
            doc_ids=request.doc_ids,
            min_technicality=request.min_technicality,
            standards_contain=request.standards_contain,
        )

        elapsed = round(time.time() - start, 3)
        logger.info(
            f"Search complete — {response['count']} results "
            f"from {response['total_raw']} candidates "
            f"in {elapsed}s"
        )
        return SearchResponse(**response)

    except Exception as e:
        logger.error(f"Search failed for query '{request.query}': {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.post("/filtered", response_model=SearchResponse)
def filtered_search(request: SearchRequest):
    """
    Same as /search but forces high technicality threshold.
    Use this for estimation and compliance queries.
    """
    start = time.time()
    logger.info(f"Filtered search: '{request.query}'")

    try:
        response = search(
            query=request.query,
            top_k=request.top_k,
            doc_ids=request.doc_ids,
            min_technicality=max(request.min_technicality, 0.6),
            standards_contain=request.standards_contain,
        )

        elapsed = round(time.time() - start, 3)
        logger.info(f"Filtered search complete — {response['count']} results in {elapsed}s")
        return SearchResponse(**response)

    except Exception as e:
        logger.error(f"Filtered search failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Filtered search failed: {str(e)}"
        )