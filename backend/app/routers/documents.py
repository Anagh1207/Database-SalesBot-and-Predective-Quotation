from fastapi import APIRouter, HTTPException
from retrieval.metadata_store import filter_chunks
from typing import List

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


@router.get("")
def list_documents():
    """
    Returns all document IDs currently in the system.
    """
    try:
        all_chunks = filter_chunks(min_technicality=0.0)
        doc_ids = sorted(set(c["doc_id"] for c in all_chunks))
        return {
            "total_documents": len(doc_ids),
            "documents": doc_ids,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not list documents: {str(e)}"
        )


@router.get("/{doc_id}")
def get_document_chunks(doc_id: str, min_technicality: float = 0.0):
    """
    Returns all chunks for a specific document.
    Useful for previewing what is indexed for a given doc.

    Example:
        GET /documents/3428ps8i2-K-Rend-K1-Spray
    """
    try:
        chunks = filter_chunks(
            doc_ids=[doc_id],
            min_technicality=min_technicality,
        )
        if not chunks:
            raise HTTPException(
                status_code=404,
                detail=f"No chunks found for doc_id: {doc_id}"
            )
        return {
            "doc_id": doc_id,
            "total_chunks": len(chunks),
            "chunks": [
                {
                    "chunk_id": c["chunk_id"],
                    "page_start": c["page_start"],
                    "page_end": c["page_end"],
                    "technicality_score": c["technicality_score"],
                    "text_preview": c["text"][:150],
                }
                for c in chunks
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not get document: {str(e)}"
        )