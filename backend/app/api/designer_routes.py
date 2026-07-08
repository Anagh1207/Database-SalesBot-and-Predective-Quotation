"""
designer_routes.py — Clean, designer-focused API endpoints for custom frontend integration.
"""
from __future__ import annotations

import logging
from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import engine, get_db
from app.models.schemas import ChatMessage, TablePayload
from text_to_sql.pipeline import run_text_to_sql

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["designer-api"])


class DesignerChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="The natural language question or message from the user.")
    history: list[ChatMessage] = Field(default_factory=list, description="Prior conversation history for carry-over context.")


class DesignerChatResponse(BaseModel):
    answer: str = Field(..., description="Markdown response containing the business explanation and reasoning with rounded EDP figures.")
    sql_query: str = Field("", description="The safe SQL SELECT statement generated and run (empty if chitchat/metadata query).")
    data_table: TablePayload | None = Field(None, description="Structured dataset matching the query results.")
    has_data: bool = Field(False, description="Boolean flag indicating if a valid tabular dataset is included.")
    error: str | None = Field(None, description="Error details if the pipeline failed or SQL was blocked by safety checks.")


@router.post("/chat", response_model=DesignerChatResponse)
def designer_chat(
    payload: DesignerChatRequest,
    db: Session = Depends(get_db),
):
    """
    Unified API Endpoint for Frontend Designers:
    
    Converts a natural language query into clean SQL, runs it against the PostgreSQL database,
    and returns a formatted Markdown response with rounded EDP currency values along with tabular data.
    """
    try:
        # We run the primary Llama pipeline
        result = run_text_to_sql(
            db=db,
            engine=engine,
            user_message=payload.message,
            history=payload.history,
            backend="llama",
        )
    except Exception as exc:
        logger.exception("Designer API call failed")
        return DesignerChatResponse(
            answer="⚠️ An unexpected server error occurred while processing your request.",
            sql_query="",
            data_table=None,
            has_data=False,
            error=str(exc),
        )

    # Prepare table payload if data is present
    table_data = result.get("table")
    table_payload = None
    has_data = False
    
    if table_data and table_data.get("columns") and table_data.get("rows"):
        table_payload = TablePayload(
            columns=table_data["columns"],
            rows=table_data["rows"],
        )
        has_data = len(table_data["rows"]) > 0

    return DesignerChatResponse(
        answer=result.get("message", "No response explanation returned."),
        sql_query=result.get("sql", ""),
        data_table=table_payload,
        has_data=has_data,
        error=result.get("error"),
    )


# ── Simplified Ask Endpoints (Returns Output Directly) ─────────────────────

from fastapi.responses import PlainTextResponse

class SimpleAskRequest(BaseModel):
    q: str = Field(..., description="The natural language question to ask.")
    format: Literal["text", "json"] = Field("text", description="Response format: 'text' returns raw string, 'json' returns flat json.")


@router.get("/ask")
def ask_get(
    q: str = Query(..., description="The query to execute."),
    format: Literal["text", "json"] = "text",
    db: Session = Depends(get_db),
):
    """
    Super-Simple GET Query Endpoint:
    
    Simply call:
    `GET /api/ask?q=What is our sales growth`
    
    By default, this returns the final markdown text answer DIRECTLY as a raw text string,
    making it extremely easy for a designer or external system to consume.
    """
    try:
        result = run_text_to_sql(
            db=db,
            engine=engine,
            user_message=q,
            history=[],
            backend="llama",
        )
        answer = result.get("message", "No response explanation returned.")
    except Exception as exc:
        logger.exception("Simple GET ask endpoint failed")
        answer = f"⚠️ Server error: {exc}"
        if format == "json":
            return {"output": answer, "error": str(exc)}
        return PlainTextResponse(content=answer, status_code=500)

    if format == "json":
        return {
            "output": answer,
            "sql": result.get("sql", ""),
            "has_table": result.get("table") is not None,
            "error": result.get("error")
        }

    return PlainTextResponse(content=answer)


@router.post("/ask")
def ask_post(
    payload: SimpleAskRequest,
    db: Session = Depends(get_db),
):
    """
    Super-Simple POST Query Endpoint:
    
    `POST /api/ask` with JSON: `{"q": "..."}`
    
    Returns the markdown text directly as a raw text response by default.
    """
    try:
        result = run_text_to_sql(
            db=db,
            engine=engine,
            user_message=payload.q,
            history=[],
            backend="llama",
        )
        answer = result.get("message", "No response explanation returned.")
    except Exception as exc:
        logger.exception("Simple POST ask endpoint failed")
        answer = f"⚠️ Server error: {exc}"
        if payload.format == "json":
            return {"output": answer, "error": str(exc)}
        return PlainTextResponse(content=answer, status_code=500)

    if payload.format == "json":
        return {
            "output": answer,
            "sql": result.get("sql", ""),
            "has_table": result.get("table") is not None,
            "error": result.get("error")
        }

    return PlainTextResponse(content=answer)
