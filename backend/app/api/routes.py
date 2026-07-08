"""
FastAPI routers for analytics and chat.
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db, engine
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    IngestResponse,
    SalesSummaryParams,
    SalespersonPerformanceParams,
    TargetAchievementParams,
    TopCustomersParams,
)
from app.query_builder.sales_analytics import run_intent_query
from app.services.chat_service import handle_chat_message
from app.services.excel_ingestion import ingest_all
from app.intent_detection.openrouter_classifier import classify_intent_with_openrouter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest, db: Session = Depends(get_db)):
    """Unified chatbot endpoint with OpenRouter intent classification."""
    session_id = payload.session_id or "default"
    
    # 1. Check for active estimation/KNN session in Construction AI
    from certiq.chatbot_bridge import is_knn_session_active
    from chatbot.estimation_flow import _sessions as legacy_sessions
    
    legacy_session = legacy_sessions.get(session_id)
    legacy_active = legacy_session is not None and not legacy_session.jobs_shown
    
    is_active_session = is_knn_session_active(session_id) or legacy_active
    
    if is_active_session:
        intent_category = "construction_ai"
    else:
        # 2. Classify intent using OpenRouter
        intent_category = classify_intent_with_openrouter(payload.message)
        
    if intent_category == "sales_lookup":
        # Call Sales Chatbot
        return handle_chat_message(db, engine, payload.message, payload.history)
    elif intent_category == "sales_text_to_sql":
        from text_to_sql.pipeline import run_text_to_sql
        from app.models.schemas import TablePayload
        
        res = run_text_to_sql(db, engine, payload.message, payload.history, backend="llama")
        
        table_payload = None
        if res.get("table"):
            table_payload = TablePayload(columns=res["table"]["columns"], rows=res["table"]["rows"])
            
        return ChatResponse(
            intent="text_to_sql",
            message=res["message"],
            needs_clarification=False,
            parameters={},
            table=table_payload,
            meta={"sql": res.get("sql"), "dynamic": True}
        )
    else:
        # Call Construction AI Chatbot
        from chatbot.orchestrator import chat as construction_chat
        
        c_resp = construction_chat(
            query=payload.message,
            session_id=session_id,
            top_k=5,
            min_technicality=0.3
        )
        
        # Adaptation of sources into pdf_links
        pdf_links = []
        if c_resp.sources:
            for idx, s in enumerate(c_resp.sources):
                pdf_links.append({
                    "id": s.get("doc_id") or f"doc-{idx}",
                    "name": s.get("source") or s.get("doc_id") or "Reference Document",
                    "generatedDate": f"Confidence: {s.get('confidence', 'N/A')}",
                    "url": "#"
                })
                
        # Adaptation of KNN prediction/jobs into similar_projects
        similar_projects = []
        if c_resp.prediction and "k_neighbors" in c_resp.prediction:
            for n in c_resp.prediction["k_neighbors"]:
                similar_projects.append({
                    "projectName": n.get("cert_id", "Unknown"),
                    "industry": n.get("company", "Roofing Client"),
                    "revenue": f"{n.get('act_hrs', 0)} hrs (Act) / Est: {n.get('est_hrs', 0)} hrs",
                    "matchScore": int(n.get("similarity", 0)),
                    "completionDate": f"Cert No: {n.get('cert_no', 'N/A')}"
                })
        elif c_resp.jobs:
            for j in c_resp.jobs:
                similar_projects.append({
                    "projectName": j.get("job_no", "Unknown"),
                    "industry": j.get("prod_type", "Liquid Applied"),
                    "revenue": f"{j.get('act_hrs', 0)} hrs",
                    "matchScore": int(100 - abs(j.get("variation", 0))),
                    "completionDate": f"Est: {j.get('est_hrs', 0)} hrs"
                })
                
        # Return format tailored for the frontend blocks parsing
        meta = {
            "intent": c_resp.intent,
            "response_time": c_resp.response_time,
            "model_used": c_resp.model_used,
            "is_estimation": c_resp.is_estimation
        }
        
        return ChatResponse(
            intent=c_resp.intent,
            message=c_resp.answer,
            needs_clarification=False,
            parameters={},
            table=None,
            meta=meta,
            similar_projects=similar_projects,
            pdf_links=pdf_links
        )


def _run(db: Session, intent: str, params: dict):
    try:
        return run_intent_query(engine, db, intent, params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sales-summary")
def sales_summary(
    customer: str | None = None,
    salesperson: str | None = None,
    year: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
):
    params = SalesSummaryParams(
        customer=customer,
        salesperson=salesperson,
        year=year,
        start_date=start_date,
        end_date=end_date,
    ).model_dump(exclude_none=True)
    return _run(db, "sales_summary", params)


@router.get("/top-customers")
def top_customers(
    limit: int = 5,
    year: int | None = None,
    quarter: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
):
    params = TopCustomersParams(limit=limit, year=year, quarter=quarter).model_dump(exclude_none=True)
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    return _run(db, "top_customers", params)


@router.get("/target-achievement")
def target_achievement(
    year: int | None = None,
    quarter: int | None = None,
    met_only: bool | None = None,
    not_met_only: bool | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
):
    params = TargetAchievementParams(
        year=year,
        quarter=quarter,
        met_only=met_only,
        not_met_only=not_met_only,
    ).model_dump(exclude_none=True)
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    return _run(db, "target_achievement", params)


@router.get("/salesperson-performance")
def salesperson_performance(
    year: int | None = None,
    quarter: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
):
    params = SalespersonPerformanceParams(year=year, quarter=quarter).model_dump(exclude_none=True)
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    return _run(db, "salesperson_performance", params)


@router.post("/admin/ingest-excel", response_model=IngestResponse)
def ingest_excel():
    """
    Load configured Excel paths into PostgreSQL (destructive replace per table).
    Intended for local/dev; protect in production (auth omitted for MVP).
    """
    try:
        counts = ingest_all(engine)
    except Exception as exc:  # pragma: no cover
        logger.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return IngestResponse(status="ok", counts=counts)


@router.get("/sales-trends")
def sales_trends(
    period: Literal["quarterly", "yearly"] = "quarterly",
    db: Session = Depends(get_db),
):
    """
    Expose quarterly or yearly sales trends for the dashboard line chart.
    """
    try:
        intent = "quarterly_sales" if period == "quarterly" else "yearly_sales"
        result = run_intent_query(engine, db, intent, {})
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
