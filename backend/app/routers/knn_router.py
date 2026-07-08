"""
KNN Router — exposes the full KNN pipeline via FastAPI.

Endpoints:
  GET  /knn/form/{product_type_id}     — get dynamic form schema
  POST /knn/infer/form                 — run KNN from form answers
  POST /knn/infer/pdf                  — run KNN from uploaded PDF
  POST /knn/infer/text                 — run KNN from text description
  GET  /knn/certs/{product_type_id}    — list all stored certs
  POST /knn/ingest                     — ingest a new cert PDF
  GET  /knn/log                        — view inference log
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import shutil
from pathlib import Path
from app.logger import get_logger

router = APIRouter(prefix="/knn", tags=["KNN Estimation"])
logger = get_logger("knn_router")


# ── REQUEST MODELS ─────────────────────────────────────────────────────────

class FormInferRequest(BaseModel):
    product_type_id: str = "LA"
    answers: Dict[str, Any]
    session_id: str = ""
    k: int = 3


class TextInferRequest(BaseModel):
    product_type_id: str = "LA"
    text: str
    session_id: str = ""
    k: int = 3


# ── ENDPOINTS ──────────────────────────────────────────────────────────────

@router.get("/form/{product_type_id}")
def get_form(product_type_id: str = "LA"):
    """
    Returns the dynamic form schema for a product type.
    The frontend uses this to render the correct form fields.
    """
    try:
        from certiq.forms import get_form_schema
        return get_form_schema(product_type_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/infer/form")
def infer_from_form(req: FormInferRequest):
    """
    Runs KNN inference from form answers.
    User fills in the dynamic form → prediction returned.
    """
    try:
        from certiq.forms import form_answers_to_vector, parse_form_answer
        from certiq.store import get_attributes
        from certiq.knn import run_knn_inference, format_knn_result

        # Parse and validate answers
        attributes = get_attributes(req.product_type_id)
        parsed = {}
        for attr in attributes:
            if attr["attr_name"] in req.answers:
                raw = req.answers[attr["attr_name"]]
                parsed[attr["attr_name"]] = parse_form_answer(
                    attr["attr_name"],
                    str(raw),
                    attr["data_type"],
                )

        # Build query vector
        query_vector = form_answers_to_vector(parsed, req.product_type_id)

        # Run KNN
        result = run_knn_inference(
            query_vector=query_vector,
            product_type_id=req.product_type_id,
            k=req.k,
            session_id=req.session_id,
            input_attributes=parsed,
            input_source="form",
        )

        result["formatted"] = format_knn_result(result)
        return result

    except Exception as e:
        logger.error(f"Form inference error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/infer/pdf")
async def infer_from_pdf(
    file: UploadFile = File(...),
    product_type_id: str = "LA",
    k: int = 3,
    session_id: str = "",
):
    """
    Uploads a test PDF and runs KNN inference.
    Full pipeline: PDF → extract attributes → KNN → prediction.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files accepted")

    upload_path = f"data/roofing_tests/{file.filename}"
    Path("data/roofing_tests").mkdir(parents=True, exist_ok=True)

    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        from certiq.knn import run_knn_on_pdf, format_knn_result
        result = run_knn_on_pdf(
            pdf_path=upload_path,
            product_type_id=product_type_id,
            k=k,
            session_id=session_id,
        )
        result["formatted"] = format_knn_result(result)
        return result
    except Exception as e:
        logger.error(f"PDF inference error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/infer/text")
def infer_from_text(req: TextInferRequest):
    """
    Runs KNN inference from a plain text description.
    User pastes email, describes job in words → prediction returned.
    """
    try:
        from certiq.parser import parse_any
        from certiq.extractor import extract_attributes, build_attr_vector
        from certiq.knn import run_knn_inference, format_knn_result

        doc          = parse_any(req.text)
        attr_results = extract_attributes(doc, req.product_type_id, use_llm=False)
        query_vector = build_attr_vector(attr_results, req.product_type_id)

        result = run_knn_inference(
            query_vector=query_vector,
            product_type_id=req.product_type_id,
            k=req.k,
            session_id=req.session_id,
            input_attributes={
                k: v for k, v in attr_results.items() if v["is_present"]
            },
            input_source="text",
        )

        result["extracted_attributes"] = attr_results
        result["formatted"]            = format_knn_result(result)
        return result

    except Exception as e:
        logger.error(f"Text inference error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/certs/{product_type_id}")
def list_certs(product_type_id: str = "LA"):
    """Lists all stored certs for a product type."""
    try:
        from certiq.store import get_all_cert_jobs
        import json
        jobs = get_all_cert_jobs(product_type_id)
        for j in jobs:
            j["attributes"] = {
                k: v for k, v in j["attributes"].items()
                if v.get("is_present")
            }
        return {"total": len(jobs), "certs": jobs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest")
async def ingest_cert(
    file: UploadFile = File(...),
    product_type_id: str = "LA",
    est_hrs: float = 40.0,
    act_hrs: float = 40.0,
):
    """Ingests a new cert PDF into the KNN store."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files accepted")

    cert_id  = file.filename.replace(".pdf", "")
    pdf_path = f"data/roofing_certs/{cert_id}.pdf"
    Path("data/roofing_certs").mkdir(parents=True, exist_ok=True)

    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        from certiq.pipeline import ingest_single_cert
        result = ingest_single_cert(
            pdf_path=pdf_path,
            cert_id=cert_id,
            product_type_id=product_type_id,
            est_hrs=est_hrs,
            act_hrs=act_hrs,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/log")
def get_inference_log(limit: int = 20):
    """Returns recent inference log entries."""
    try:
        import sqlite3
        from app.config import settings
        conn = sqlite3.connect(settings.DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM knn_inference_log
            ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return {"total": len(rows), "logs": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/product-types")
def list_product_types():
    """Lists all product types in the registry."""
    try:
        from certiq.store import get_connection
        conn = get_connection()
        rows = conn.execute("""
            SELECT pt.*, COUNT(a.attr_id) as attr_count,
                   COUNT(j.job_id) as cert_count
            FROM knn_product_types pt
            LEFT JOIN knn_attributes a ON pt.product_type_id = a.product_type_id
            LEFT JOIN knn_cert_jobs  j ON pt.product_type_id = j.product_type_id
            GROUP BY pt.product_type_id
        """).fetchall()
        conn.close()
        return {"product_types": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))