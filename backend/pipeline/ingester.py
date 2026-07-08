import json
import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

import faiss
from sentence_transformers import SentenceTransformer

from pipeline.pdf_reader import read_pdf, get_pdf_info
from pipeline.chunker import chunk_by_structure
from pipeline.extractor_layer1 import process_chunks_layer1
from pipeline.extractor_layer2 import process_chunks_layer2
from retrieval.data_loader import Chunk
from retrieval.metadata_store import insert_chunks, init_db
from app.config import settings
from app.logger import get_logger

logger = get_logger("ingester")


def convert_to_chunk_objects(
    enriched_chunks: List[Dict[str, Any]]
) -> List[Chunk]:
    """
    Converts enriched pipeline chunks into Chunk dataclass objects
    that the retrieval system understands.
    Merges Layer 1 and Layer 2 extracted data.
    """
    chunks = []

    for c in enriched_chunks:
        l1 = c.get("layer1", {})
        l2 = c.get("layer2", {})

        # Merge standards from both layers
        standards = list(set(
            l1.get("standards", []) +
            l2.get("standards", [])
        ))

        chunk = Chunk(
            chunk_id=c["chunk_id"],
            doc_id=c["doc_id"],
            window_id=c["window_id"],
            page_start=c["page_start"],
            page_end=c["page_end"],
            text=c["text"],
            technicality_score=c.get("technicality_score", 0.0),
            product_names=l2.get("product_name", []),
            technical_entities=l2.get("technical_entities", []),
            functional_properties=l2.get("functional_properties", []),
            standards=standards,
            constraints=l2.get("constraints", []) + l1.get("dimensions", []),
            performance_characteristics=l2.get("performance_characteristics", []),
            object_names=l2.get("object_name", []),
        )
        chunks.append(chunk)

    return chunks


def save_to_json(
    enriched_chunks: List[Dict[str, Any]],
    doc_id: str,
    output_dir: str = "data/processed",
) -> str:
    """
    Saves enriched chunks to a JSON file.
    Useful for inspection and backup.
    Returns the path to the saved file.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = f"{output_dir}/{doc_id}.json"

    # Build output in your schema format
    output = []
    for i, c in enumerate(enriched_chunks):
        l1 = c.get("layer1", {})
        l2 = c.get("layer2", {})

        record = {
            "chunk_id": c["chunk_id"],
            "doc_id": c["doc_id"],
            "window_id": c["window_id"],
            "page_start": c["page_start"],
            "page_end": c["page_end"],
            "text": c["text"],
            "technicality_score": c.get("technicality_score", 0.0),
            "metadata": {
                "object_name": l2.get("object_name", []),
                "product_name": l2.get("product_name", []),
                "technical_entities": l2.get("technical_entities", []),
                "functional_properties": l2.get("functional_properties", []),
                "standards": list(set(
                    l1.get("standards", []) +
                    l2.get("standards", [])
                )),
                "constraints": l2.get("constraints", []),
                "performance_characteristics": l2.get("performance_characteristics", []),
                "application_scope": l2.get("application_scope", []),
                "layer1_cert_no": l1.get("cert_no", []),
                "layer1_dimensions": l1.get("dimensions", []),
                "layer1_temperatures": l1.get("temperatures", []),
                "layer1_regulation_refs": l1.get("regulation_refs", []),
            }
        }
        output.append(record)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"✅ Saved {len(output)} chunks to {output_path}")
    return output_path


def update_faiss_index(
    new_chunks: List[Chunk],
    faiss_path: str = settings.FAISS_PATH,
    id_map_path: str = settings.ID_MAP_PATH,
    embeddings_cache: str = settings.EMBEDDINGS_CACHE,
) -> int:
    """
    Adds new chunk embeddings to the existing FAISS index.
    Returns the new total number of vectors.
    """
    logger.info(f"Updating FAISS index with {len(new_chunks)} new chunks...")

    # Load existing index and id map
    index = faiss.read_index(faiss_path)
    with open(id_map_path, "rb") as f:
        chunk_ids = pickle.load(f)

    # Check for duplicates
    existing_ids = set(chunk_ids)
    truly_new = [c for c in new_chunks if c.chunk_id not in existing_ids]

    if not truly_new:
        logger.info("No new chunks to add — all already indexed")
        return index.ntotal

    # Embed new chunks
    model = SentenceTransformer(settings.MODEL_NAME)
    texts = [c.text for c in truly_new]
    new_embeddings = model.encode(
        texts,
        batch_size=settings.BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)

    # Add to index
    index.add(new_embeddings)
    chunk_ids.extend([c.chunk_id for c in truly_new])

    # Save updated index and id map
    faiss.write_index(index, faiss_path)
    with open(id_map_path, "wb") as f:
        pickle.dump(chunk_ids, f)

    # Update embeddings cache
    with open(embeddings_cache, "rb") as f:
        cache = pickle.load(f)

    all_embeddings = np.vstack([cache["embeddings"], new_embeddings])
    updated_cache = {
        "embeddings": all_embeddings,
        "chunk_ids": chunk_ids,
    }
    with open(embeddings_cache, "wb") as f:
        pickle.dump(updated_cache, f)

    logger.info(f"✅ FAISS index updated — {index.ntotal} total vectors")
    return index.ntotal


def ingest_pdf(
    pdf_path: str,
    doc_id: str = None,
    run_layer2: bool = True,
    save_json: bool = True,
) -> Dict[str, Any]:
    """
    Full ingestion pipeline for a single PDF.

    Steps:
    1. Read PDF
    2. Structural chunking
    3. Layer 1 deterministic extraction
    4. Layer 2 semantic extraction (Groq)
    5. Convert to Chunk objects
    6. Save to SQLite
    7. Update FAISS index
    8. Save JSON backup

    Returns a summary dict.
    """
    start = datetime.now()
    pdf_path = str(pdf_path)
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Auto-generate doc_id from filename if not provided
    if not doc_id:
        doc_id = path.stem.replace(" ", "_").replace("-", "_")

    logger.info(f"\n{'='*50}")
    logger.info(f"Starting ingestion: {path.name}")
    logger.info(f"Doc ID: {doc_id}")
    logger.info(f"{'='*50}")

    # ── STEP 1: READ PDF ───────────────────────────────────────────────────
    info = get_pdf_info(pdf_path)
    logger.info(f"PDF info: {info['page_count']} pages, {info['file_size_kb']} KB")
    pages = read_pdf(pdf_path)

    # ── STEP 2: STRUCTURAL CHUNKING ────────────────────────────────────────
    chunks = chunk_by_structure(pages, doc_id)

    # ── STEP 3: LAYER 1 EXTRACTION ─────────────────────────────────────────
    chunks = process_chunks_layer1(chunks)

    # ── STEP 4: LAYER 2 EXTRACTION ─────────────────────────────────────────
    if run_layer2:
        chunks = process_chunks_layer2(chunks)
    else:
        logger.info("Skipping Layer 2 (run_layer2=False)")
        for chunk in chunks:
            chunk["layer2"] = {field: [] for field in [
                "technical_entities", "functional_properties",
                "standards", "application_scope", "constraints",
                "performance_characteristics", "object_name", "product_name"
            ]}

    # ── STEP 5: CONVERT TO CHUNK OBJECTS ───────────────────────────────────
    chunk_objects = convert_to_chunk_objects(chunks)

    # ── STEP 6: SAVE TO SQLITE ─────────────────────────────────────────────
    init_db()
    insert_chunks(chunk_objects)

    # ── STEP 7: UPDATE FAISS INDEX ─────────────────────────────────────────
    new_total = update_faiss_index(chunk_objects)

    # ── STEP 8: SAVE JSON BACKUP ───────────────────────────────────────────
    json_path = None
    if save_json:
        json_path = save_to_json(chunks, doc_id)

    elapsed = (datetime.now() - start).total_seconds()

    summary = {
        "doc_id": doc_id,
        "pdf_path": pdf_path,
        "pages_read": len(pages),
        "chunks_created": len(chunks),
        "chunks_inserted": len(chunk_objects),
        "faiss_total_vectors": new_total,
        "json_backup": json_path,
        "processing_time_seconds": round(elapsed, 2),
        "status": "success",
    }

    logger.info(f"\n✅ Ingestion complete for {path.name}")
    logger.info(f"   Pages     : {summary['pages_read']}")
    logger.info(f"   Chunks    : {summary['chunks_created']}")
    logger.info(f"   Vectors   : {summary['faiss_total_vectors']}")
    logger.info(f"   Time      : {summary['processing_time_seconds']}s")

    return summary


def ingest_folder(
    folder_path: str = "pdfs",
    run_layer2: bool = True,
) -> List[Dict[str, Any]]:
    """
    Ingests all PDFs in a folder.
    Skips PDFs that are already indexed.
    """
    folder = Path(folder_path)
    pdfs = list(folder.glob("*.pdf"))

    if not pdfs:
        logger.warning(f"No PDFs found in {folder_path}")
        return []

    logger.info(f"Found {len(pdfs)} PDFs in {folder_path}")
    summaries = []

    for pdf_path in pdfs:
        try:
            summary = ingest_pdf(str(pdf_path), run_layer2=run_layer2)
            summaries.append(summary)
        except Exception as e:
            logger.error(f"Failed to ingest {pdf_path.name}: {e}")
            summaries.append({
                "doc_id": pdf_path.stem,
                "status": "failed",
                "error": str(e),
            })

    success = sum(1 for s in summaries if s.get("status") == "success")
    logger.info(f"\n✅ Folder ingestion complete — {success}/{len(pdfs)} successful")
    return summaries