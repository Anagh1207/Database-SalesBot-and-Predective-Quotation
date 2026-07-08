from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from chatbot.orchestrator import chat
from app.logger import get_logger

router = APIRouter(
    prefix="/chat",
    tags=["Chatbot"],
)

logger = get_logger("chat_router")


class ChatRequest(BaseModel):
    message: str = Field(..., example="We got a project to quote for testing plasterboard")
    session_id: str = Field(default="default", description="Session ID for multi-turn conversations")
    top_k: int = Field(default=5, ge=1, le=20)
    min_technicality: float = Field(default=0.3, ge=0.0, le=1.0)


class SourceReference(BaseModel):
    source: str
    doc_id: str
    confidence: str
    fused_score: float
    standards: List[str]


class JobResult(BaseModel):
    job_no: str
    prod_type: str
    job_type: str
    est_hrs: float
    act_hrs: float
    variation: float
    variation_label: str
    # NOTE: 'status' removed — column does not exist in the timesheet


class ChatResponseModel(BaseModel):
    answer: str
    intent: str
    confidence: float
    sources: List[SourceReference]
    total_chunks_searched: int
    response_time: float
    model_used: str
    jobs: List[Dict[str, Any]] = []
    jobs_table: str = ""
    is_estimation: bool = False
    prediction: Optional[Dict[str, Any]] = None      # ← KNN prediction result





@router.post("/reset")
def reset_session(session_id: str = "default"):
    """Resets all estimation sessions for this session_id."""
    # Reset legacy estimation session
    from chatbot.estimation_flow import clear_session
    clear_session(session_id)

    # Reset KNN inference session
    try:
        from certiq.inference import clear_session as knn_clear_session
        knn_clear_session(session_id)
    except Exception:
        pass

    return {"message": f"Session {session_id} reset successfully"}


@router.get("/health")
def chat_health():
    """Quick check that the chatbot and KNN store are ready."""
    from chatbot.llm_client import test_connection
    ok = test_connection()

    knn_status = "unknown"
    knn_certs  = 0
    try:
        from certiq.store import get_all_cert_jobs
        jobs       = get_all_cert_jobs("LA")
        knn_certs  = len(jobs)
        knn_status = "ready" if knn_certs > 0 else "empty"
    except Exception:
        knn_status = "unavailable"

    return {
        "status":        "ok" if ok else "error",
        "groq_connected": ok,
        "knn_store":     knn_status,
        "knn_certs":     knn_certs,
        "message":       (
            f"Chatbot ready — KNN store: {knn_status} ({knn_certs} certs)"
            if ok else "Groq connection failed"
        ),
    }