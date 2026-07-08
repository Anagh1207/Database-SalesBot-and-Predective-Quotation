"""
KNN Prediction Router — Live Inference Pipeline

Uses certiq/knn.py functions directly:
  run_knn_inference()  — for form/chat input (vector-based)
  run_knn_on_pdf()     — for PDF upload

Flow:
  Form / Chat / PDF Upload
       ↓
  This Router (parse input → build vector)
       ↓
  certiq/knn.py → run_knn_inference() (Gower distance KNN)
       ↓
  Estimate + Similar Jobs + Explanation → Frontend
"""

import os
import uuid
import tempfile
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel, Field
from app.logger import get_logger

router = APIRouter(prefix="/knn", tags=["KNN Estimation"])
logger = get_logger("knn_router")


# ══════════════════════════════════════════════════════════════════
# REQUEST MODELS
# ══════════════════════════════════════════════════════════════════

class FormPredictRequest(BaseModel):
    product_type_id: str = Field(default="LA")
    form_data: Dict[str, Any] = Field(
        ...,
        example={
            "weathertightness": True,
            "properties_in_relation_to_fire": True,
            "resistance_to_wind_uplift": True,
            "resistance_to_mechanical_damage": True,
            "resistance_to_penetration_of_roots": False,
            "durability": 25,
            "protection_against_noise": False,
            "adhesion": True,
            "slip_resistance": False,
            "regulations": True,
        }
    )
    k: int = Field(default=3, ge=1, le=6)
    session_id: Optional[str] = None


class ChatPredictRequest(BaseModel):
    product_type_id: str = Field(default="LA")
    message: str = Field(
        ...,
        example="I need a weathertight fire rated roof with 25 year durability and wind uplift resistance"
    )
    k: int = Field(default=3, ge=1, le=6)
    session_id: Optional[str] = None


# ══════════════════════════════════════════════════════════════════
# SHARED HELPER — converts raw result to unified response shape
# ══════════════════════════════════════════════════════════════════

def _build_response(result: Dict[str, Any], session_id: str, input_source: str) -> Dict[str, Any]:
    """
    Converts run_knn_inference() output → clean unified response
    that matches what KNNResultCard in the frontend expects.

    run_knn_inference returns:
      predicted_hrs, confidence, best_similarity,
      k_neighbors: [{cert_id, company, cert_no, distance,
                     similarity, est_hrs, act_hrs, variation}],
      explanation
    """
    neighbors = result.get("k_neighbors", [])

    # Build similar_jobs in the shape the frontend KNNResultCard expects
    similar_jobs = [
        {
            "cert_id":        n["cert_id"],
            "company":        n.get("company", ""),
            "cert_no":        n.get("cert_no", ""),
            "distance":       round(n["distance"], 4),
            "similarity_pct": n["similarity"],          # already a percentage
            "est_hrs":        n["est_hrs"],
            "act_hrs":        n["act_hrs"],
            "variation":      n["variation"],
        }
        for n in neighbors
    ]

    return {
        "session_id":      session_id,
        "product_type_id": result.get("product_type_id", "LA"),
        "predicted_hrs":   result.get("predicted_hrs", 0.0),
        "confidence":      result.get("confidence", "LOW"),
        "best_similarity": result.get("best_similarity", 0.0),
        "k_used":          len(neighbors),
        "similar_jobs":    similar_jobs,
        "explanation":     result.get("explanation", ""),
        "input_source":    input_source,
    }


# ══════════════════════════════════════════════════════════════════
# UTILITY ENDPOINTS
# ══════════════════════════════════════════════════════════════════

@router.get(
    "/form-schema/{product_type_id}",
    summary="Get dynamic form schema",
)
def get_form_schema(product_type_id: str = "LA"):
    try:
        from certiq.forms import get_form_schema
        return get_form_schema(product_type_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Form schema error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/store/summary",
    summary="KNN data store summary",
)
def get_store_summary(product_type_id: str = Query(default="LA")):
    try:
        from certiq.store import get_all_cert_jobs, get_attributes
        jobs  = get_all_cert_jobs(product_type_id)
        attrs = get_attributes(product_type_id)
        return {
            "product_type_id": product_type_id,
            "total":           len(jobs),
            "attributes":      len(attrs),
            "certs":           [
                {
                    "cert_id": j["cert_id"],
                    "company": j.get("company", ""),
                    "est_hrs": j["est_hrs"],
                    "act_hrs": j["act_hrs"],
                }
                for j in jobs
            ],
        }
    except Exception as e:
        logger.error(f"Store summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/store/attribute-matrix",
    summary="Visual attribute matrix for the dashboard",
)
def get_attribute_matrix(product_type_id: str = Query(default="LA")):
    try:
        from certiq.store import get_all_cert_jobs, get_attributes

        jobs  = get_all_cert_jobs(product_type_id)
        attrs = get_attributes(product_type_id)

        if not jobs:
            raise HTTPException(status_code=404, detail="No certs ingested yet.")

        attr_names = [a["attr_name"] for a in attrs]
        matrix = []
        for job in jobs:
            row = {
                "cert_id":   job["cert_id"],
                "company":   job.get("company", ""),
                "cert_no":   job.get("cert_no", ""),
                "est_hrs":   job["est_hrs"],
                "act_hrs":   job["act_hrs"],
                "variation": job["variation"],
            }
            # Build attribute flags from the attr_vector
            vec = job.get("attr_vector", [])
            for i, attr_name in enumerate(attr_names):
                row[attr_name] = bool(vec[i]) if i < len(vec) else False
            matrix.append(row)

        return {
            "product_type_id": product_type_id,
            "attributes":      [{"attr_name": a["attr_name"], "display_name": a["display_name"]} for a in attrs],
            "matrix":          matrix,
            "total_certs":     len(matrix),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Attribute matrix error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/inference-log",
    summary="View all past predictions",
)
def get_inference_log(
    product_type_id: str = Query(default="LA"),
    limit: int = Query(default=50, ge=1, le=500),
):
    try:
        from certiq.store import get_connection, DB_PATH
        import json

        conn = get_connection(DB_PATH)
        rows = conn.execute("""
            SELECT log_id, session_id, product_type_id, input_source,
                   input_attributes, k_neighbors, predicted_hrs,
                   confidence, created_at
            FROM   knn_inference_log
            WHERE  product_type_id = ?
            ORDER  BY created_at DESC
            LIMIT  ?
        """, (product_type_id, limit)).fetchall()
        conn.close()

        return {
            "product_type_id": product_type_id,
            "total": len(rows),
            "logs": [
                {
                    "log_id":           r["log_id"],
                    "session_id":       r["session_id"],
                    "input_source":     r["input_source"],
                    "predicted_hrs":    r["predicted_hrs"],
                    "confidence":       r["confidence"],
                    "k_neighbors":      r["k_neighbors"],
                    "input_attributes": json.loads(r["input_attributes"] or "{}"),
                    "created_at":       r["created_at"],
                }
                for r in rows
            ],
        }
    except Exception as e:
        logger.error(f"Inference log error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════
# PREDICTION — FORM
# ══════════════════════════════════════════════════════════════════

@router.post(
    "/predict/form",
    summary="Predict from form submission",
)
def predict_from_form(req: FormPredictRequest):
    """
    User filled the dynamic assessment form →
    parse → build attr vector → run_knn_inference → return estimate.
    """
    try:
        from certiq.forms import parse_form_submission, validate_form_submission
        from certiq.extractor import build_attr_vector
        from certiq.knn import run_knn_inference

        session_id = req.session_id or str(uuid.uuid4())

        # Validate required fields
        validation = validate_form_submission(req.form_data, req.product_type_id)
        if not validation["valid"]:
            raise HTTPException(
                status_code=422,
                detail={"message": "Required fields missing.", "errors": validation["errors"]}
            )

        # Parse form → flat {attr_name: True/False or float}
        parsed_attrs = parse_form_submission(req.form_data, req.product_type_id)

        # Convert to attr_results format that build_attr_vector expects
        # build_attr_vector expects: {attr_name: {"is_present": bool, "value": any}}
        attr_results = {
            name: {"is_present": bool(val) if not isinstance(val, float) else val > 0,
                   "value": val if isinstance(val, float) else None,
                   "confidence": 1.0}
            for name, val in parsed_attrs.items()
        }

        # Build float vector for Gower distance
        query_vector = build_attr_vector(attr_results, req.product_type_id)

        # Run KNN
        result = run_knn_inference(
            query_vector=query_vector,
            product_type_id=req.product_type_id,
            k=req.k,
            session_id=session_id,
            input_attributes=parsed_attrs,
            input_source="form",
        )

        response = _build_response(result, session_id, "form")
        response["validation_warnings"] = validation.get("warnings", [])
        response["input_attributes"]    = parsed_attrs

        logger.info(
            f"[FORM] session={session_id} | "
            f"predicted={response['predicted_hrs']}h | "
            f"confidence={response['confidence']}"
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Form predict error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════
# PREDICTION — CHAT
# ══════════════════════════════════════════════════════════════════

@router.post(
    "/predict/chat",
    summary="Predict from chatbot free-text message",
)
def predict_from_chat(req: ChatPredictRequest):
    """
    User typed a free-text message →
    keyword extraction → build vector → run_knn_inference.
    """
    try:
        from certiq.forms import parse_chatbot_attrs
        from certiq.extractor import build_attr_vector
        from certiq.knn import run_knn_inference

        session_id = req.session_id or str(uuid.uuid4())

        # Extract attributes from natural language
        parsed_attrs = parse_chatbot_attrs(req.message, req.product_type_id)
        active_attrs = [k for k, v in parsed_attrs.items() if v]

        if not active_attrs:
            return {
                "session_id":           session_id,
                "predicted_hrs":        None,
                "confidence":           "NONE",
                "similar_jobs":         [],
                "explanation":          "No technical attributes detected in your message.",
                "suggestion":           "Try: 'weathertight, fire rated, 25 year durability, wind uplift'",
                "extracted_attributes": parsed_attrs,
                "input_source":         "chatbot",
            }

        # Build attr_results → vector
        attr_results = {
            name: {"is_present": bool(val) if not isinstance(val, float) else val > 0,
                   "value": val if isinstance(val, float) else None,
                   "confidence": 1.0}
            for name, val in parsed_attrs.items()
        }
        query_vector = build_attr_vector(attr_results, req.product_type_id)

        # Run KNN
        result = run_knn_inference(
            query_vector=query_vector,
            product_type_id=req.product_type_id,
            k=req.k,
            session_id=session_id,
            input_attributes=parsed_attrs,
            input_source="chatbot",
        )

        response = _build_response(result, session_id, "chatbot")
        response["extracted_attributes"] = parsed_attrs
        response["attributes_detected"]  = active_attrs

        logger.info(
            f"[CHAT] session={session_id} | "
            f"detected={len(active_attrs)} attrs | "
            f"predicted={response['predicted_hrs']}h | "
            f"confidence={response['confidence']}"
        )
        return response

    except Exception as e:
        logger.error(f"Chat predict error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════
# PREDICTION — PDF UPLOAD
# ══════════════════════════════════════════════════════════════════

@router.post(
    "/predict/pdf",
    summary="Predict from uploaded PDF certificate",
)
async def predict_from_pdf(
    file: UploadFile = File(...),
    product_type_id: str = Query(default="LA"),
    k: int = Query(default=3, ge=1, le=6),
    session_id: Optional[str] = Query(default=None),
):
    """
    User uploads a test PDF →
    run_knn_on_pdf() handles parse + extract + vector + KNN in one call.
    This is the Test1–Test6 flow.
    """
    tmp_path = None
    try:
        from certiq.knn import run_knn_on_pdf

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

        session_id = session_id or str(uuid.uuid4())

        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content  = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        logger.info(f"[PDF] Processing: {file.filename} ({len(content)} bytes)")

        # run_knn_on_pdf handles everything: parse → extract → vector → KNN
        result = run_knn_on_pdf(
            pdf_path=tmp_path,
            product_type_id=product_type_id,
            k=k,
            use_llm=False,
            session_id=session_id,
        )

        response = _build_response(result, session_id, "pdf")

        # Add PDF-specific metadata
        response["pdf_info"] = {
            "filename":        file.filename,
            "cert_no":         result.get("cert_no", ""),
            "company":         result.get("company", ""),
            "attrs_extracted": sum(
                1 for v in result.get("extracted_attributes", {}).values()
                if v.get("is_present")
            ),
            "attrs_total": 10,
        }
        response["extracted_attributes"] = {
            k: {
                "is_present": v["is_present"],
                "confidence": round(v.get("confidence", 0.0), 2),
                "value":      v.get("value"),
            }
            for k, v in result.get("extracted_attributes", {}).items()
        }

        logger.info(
            f"[PDF] {file.filename} | "
            f"attrs={response['pdf_info']['attrs_extracted']}/10 | "
            f"predicted={response['predicted_hrs']}h | "
            f"confidence={response['confidence']}"
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF predict error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ══════════════════════════════════════════════════════════════════
# LIVE CERT INGESTION
# ══════════════════════════════════════════════════════════════════

@router.post(
    "/ingest/cert",
    summary="Add a new cert to KNN store (no retraining needed)",
)
async def ingest_new_cert(
    file: UploadFile = File(...),
    cert_id: str   = Query(..., example="Cert7"),
    product_type_id: str = Query(default="LA"),
    est_hrs: float = Query(default=40.0, ge=0),
    act_hrs: float = Query(default=40.0, ge=0),
):
    """
    Boss spec: 'no retraining as more documents get added'.
    Upload a new cert PDF → extract attributes → store in KNN table.
    All future predictions automatically consider this cert.
    """
    tmp_path = None
    try:
        from certiq.pipeline import ingest_single_cert
        from certiq.store import get_all_cert_jobs

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

        # Check for duplicate
        existing = get_all_cert_jobs(product_type_id)
        if any(j["cert_id"] == cert_id for j in existing):
            raise HTTPException(
                status_code=409,
                detail=f"Cert '{cert_id}' already exists. Use a different cert_id."
            )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content  = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        logger.info(f"[INGEST] New cert: {cert_id} | est={est_hrs}h act={act_hrs}h")

        result   = ingest_single_cert(
            pdf_path=tmp_path,
            cert_id=cert_id,
            product_type_id=product_type_id,
            est_hrs=est_hrs,
            act_hrs=act_hrs,
        )

        all_jobs = get_all_cert_jobs(product_type_id)
        logger.info(f"[INGEST] ✅ {cert_id} added | KNN store now has {len(all_jobs)} certs")

        return {
            "status":         "ingested",
            "cert_id":        cert_id,
            "result":         result,
            "knn_store_size": len(all_jobs),
            "message":        f"✅ {cert_id} added. KNN store now has {len(all_jobs)} certs — all future predictions improved.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingest error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)