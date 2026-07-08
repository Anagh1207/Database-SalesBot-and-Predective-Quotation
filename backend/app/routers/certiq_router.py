"""
CertIQ API Router — exposes the KNN pipeline via HTTP

Endpoints:
  GET  /certiq/form/{product_type_id}     — get dynamic form fields
  POST /certiq/infer/form                 — infer from form submission
  POST /certiq/infer/text                 — infer from plain text
  POST /certiq/infer/pdf                  — infer from uploaded PDF
  POST /certiq/ingest                     — ingest a new cert PDF
  GET  /certiq/certs                      — list all ingested certs
  GET  /certiq/product-types              — list all product types
  GET  /certiq/inference-log              — view inference history
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import shutil
from pathlib import Path
from app.logger import get_logger

router = APIRouter(prefix="/certiq", tags=["CertIQ — KNN Estimation"])
logger = get_logger("certiq_router")


# ── REQUEST MODELS ─────────────────────────────────────────────────────────

class FormInferRequest(BaseModel):
    product_type_id: str = "LA"
    form_data: Dict[str, Any]
    k: int = 3
    session_id: str = ""


class TextInferRequest(BaseModel):
    text: str
    product_type_id: str = "LA"
    k: int = 3
    session_id: str = ""


# ── ENDPOINTS ──────────────────────────────────────────────────────────────

@router.get("/form/{product_type_id}")
def get_form(product_type_id: str = "LA"):
    """
    Returns the dynamic form definition for a product type.
    Frontend uses this to render the correct input fields.
    """
    try:
        from certiq.forms import get_dynamic_form
        form = get_dynamic_form(product_type_id)
        if "error" in form:
            raise HTTPException(status_code=404, detail=form["error"])
        return form
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/infer/form")
def infer_from_form(req: FormInferRequest):
    """
    Runs KNN inference from a filled-in form.
    Returns predicted hours + similar certs.
    """
    try:
        from certiq.forms import run_inference_from_form, format_form_result
        result = run_inference_from_form(
            form_data=req.form_data,
            product_type_id=req.product_type_id,
            k=req.k,
            session_id=req.session_id,
        )
        result["formatted"] = format_form_result(result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/infer/text")
def infer_from_text(req: TextInferRequest):
    """
    Runs KNN inference from plain text (email, chatbot message).
    Extracts attributes then runs KNN.
    """
    try:
        from certiq.forms import run_inference_from_text, format_form_result
        result = run_inference_from_text(
            text=req.text,
            product_type_id=req.product_type_id,
            k=req.k,
            session_id=req.session_id,
        )
        result["formatted"] = format_form_result(result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/infer/pdf")
async def infer_from_pdf(
    file: UploadFile = File(...),
    product_type_id: str = Form(default="LA"),
    k: int = Form(default=3),
    session_id: str = Form(default=""),
):
    """
    Upload a test PDF and get KNN-based effort estimate.
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
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest")
async def ingest_cert(
    file: UploadFile = File(...),
    product_type_id: str = Form(default="LA"),
    est_hrs: float = Form(default=40.0),
    act_hrs: float = Form(default=40.0),
):
    """
    Ingest a new cert PDF into the KNN store.
    No retraining needed — KNN updates automatically.
    """
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
        return {"message": f"✅ {cert_id} ingested", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/certs")
def list_certs(product_type_id: str = "LA"):
    """Returns all ingested certs with their attribute profiles."""
    try:
        from certiq.pipeline import get_pipeline_summary
        return get_pipeline_summary(product_type_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/product-types")
def list_product_types():
    """Returns all available product types."""
    try:
        import sqlite3, json
        from app.config import settings
        conn = sqlite3.connect(settings.DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT pt.*, COUNT(a.attr_id) as attr_count,
                   COUNT(j.job_id) as cert_count
            FROM knn_product_types pt
            LEFT JOIN knn_attributes a ON pt.product_type_id = a.product_type_id
            LEFT JOIN knn_cert_jobs j  ON pt.product_type_id = j.product_type_id
            GROUP BY pt.product_type_id
        """).fetchall()
        conn.close()
        return {"product_types": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/inference-log")
def get_inference_log(limit: int = 20):
    """Returns recent inference history."""
    try:
        import sqlite3, json
        from app.config import settings
        conn = sqlite3.connect(settings.DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM knn_inference_log
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        results = []
        for r in rows:
            d = dict(r)
            d["matched_jobs"]     = json.loads(d["matched_jobs"]     or "[]")
            d["input_attributes"] = json.loads(d["input_attributes"] or "{}")
            results.append(d)
        return {"total": len(results), "logs": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))