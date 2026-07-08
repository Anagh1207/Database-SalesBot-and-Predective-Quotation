from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
import shutil
from pathlib import Path
from app.logger import get_logger

router = APIRouter(
    prefix="/ingest",
    tags=["Ingestion"],
)

logger = get_logger("ingest_router")


class IngestResponse(BaseModel):
    doc_id: str
    pages_read: int
    chunks_created: int
    chunks_inserted: int
    faiss_total_vectors: int
    processing_time_seconds: float
    status: str


@router.post("/pdf", response_model=IngestResponse)
async def ingest_pdf_endpoint(
    file: UploadFile = File(...),
    run_layer2: bool = True,
):
    """
    Upload and ingest a PDF into the knowledge base.
    The PDF will be processed and added to the search index.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted"
        )

    # Save uploaded file to pdfs folder (or /tmp/pdfs on Vercel)
    import os
    base_dir = "/tmp/pdfs" if os.environ.get("VERCEL") else "pdfs"
    Path(base_dir).mkdir(exist_ok=True)
    pdf_path = f"{base_dir}/{file.filename}"

    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    logger.info(f"PDF uploaded: {file.filename}")

    try:
        from pipeline.ingester import ingest_pdf
        summary = ingest_pdf(pdf_path, run_layer2=run_layer2)
        return IngestResponse(**{
            k: summary[k] for k in IngestResponse.model_fields
        })
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}"
        )


@router.post("/folder")
async def ingest_folder_endpoint(run_layer2: bool = True):
    """
    Ingest all PDFs currently in the pdfs/ folder.
    """
    try:
        from pipeline.ingester import ingest_folder
        summaries = ingest_folder(run_layer2=run_layer2)
        return {
            "total_processed": len(summaries),
            "successful": sum(1 for s in summaries if s.get("status") == "success"),
            "failed": sum(1 for s in summaries if s.get("status") == "failed"),
            "summaries": summaries,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Folder ingestion failed: {str(e)}"
        )