"""
Offline Pipeline — runs when new cert documents are added.

Steps (from boss's architecture diagram):
1. Read cert PDF
2. AI extraction → structured attributes
3. Join with job cost data (est_hrs, act_hrs)
4. Store in KNN data store

Run periodically as new jobs are added.
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from certiq.parser import parse_any
from certiq.extractor import extract_attributes, build_attr_vector
from certiq.store import (
    setup_knn_tables, seed_roofing_product_type,
    upsert_cert_job, get_all_cert_jobs, get_attributes,
    DB_PATH,
)
from app.logger import get_logger

logger = get_logger("pipeline")


# ── KNOWN CERT DATA (from Attributes and Match %.xlsx) ────────────────────
# est_hrs and act_hrs come from the Excel file your boss provided
CERT_REGISTRY = {
    "Cert1": {"est_hrs": 40.0, "act_hrs": 50.0},
    "Cert2": {"est_hrs": 50.0, "act_hrs": 25.0},
    "Cert3": {"est_hrs": 75.0, "act_hrs": 100.0},
    "Cert4": {"est_hrs": 60.0, "act_hrs": 50.0},
    "Cert5": {"est_hrs": 50.0, "act_hrs": 25.0},
    "Cert6": {"est_hrs": 60.0, "act_hrs": 40.0},  # Cert6 added
}


def run_offline_pipeline(
    cert_dir: str = "data/roofing_certs",
    product_type_id: str = "LA",
    use_llm: bool = False,
) -> List[Dict[str, Any]]:
    """
    Main offline pipeline.
    Processes all cert PDFs in cert_dir and stores in KNN store.

    Args:
        cert_dir: folder containing cert PDFs
        product_type_id: product type to use for attribute extraction
        use_llm: whether to use Groq for Pass 2 extraction

    Returns list of ingestion results.
    """
    cert_path = Path(cert_dir)
    if not cert_path.exists():
        raise FileNotFoundError(f"Cert directory not found: {cert_dir}")

    pdfs = sorted(cert_path.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDF files found in {cert_dir}")

    logger.info(f"Starting offline pipeline — {len(pdfs)} PDFs found")

    results = []
    for pdf_path in pdfs:
        cert_id = pdf_path.stem  # e.g. "Cert1"
        result  = ingest_single_cert(
            pdf_path=str(pdf_path),
            cert_id=cert_id,
            product_type_id=product_type_id,
            use_llm=use_llm,
        )
        results.append(result)

    logger.info(f"✅ Offline pipeline complete — {len(results)} certs ingested")
    return results


def ingest_single_cert(
    pdf_path: str,
    cert_id: str,
    product_type_id: str = "LA",
    est_hrs: float = None,
    act_hrs: float = None,
    use_llm: bool = False,
) -> Dict[str, Any]:
    """
    Ingests a single cert PDF into the KNN store.
    Can be called from the API when a new cert is uploaded.
    """
    # Get hours from registry if not provided
    if est_hrs is None or act_hrs is None:
        registry_entry = CERT_REGISTRY.get(cert_id, {})
        est_hrs = est_hrs or registry_entry.get("est_hrs", 40.0)
        act_hrs = act_hrs or registry_entry.get("act_hrs", 40.0)

    logger.info(f"Ingesting {cert_id} from {pdf_path}")

    # Step 1 — Parse document
    doc = parse_any(pdf_path)

    # Fix company extraction — search first 30 non-empty lines
    company = _extract_company(doc.raw_text)

    # Step 2 — Extract attributes
    attr_results = extract_attributes(
        doc,
        product_type_id=product_type_id,
        use_llm=use_llm,
    )

    # Step 3 — Build attribute vector for KNN
    attr_vector = build_attr_vector(attr_results, product_type_id)

    # Step 4 — Store in KNN data store
    job = {
        "job_id":          cert_id,
        "product_type_id": product_type_id,
        "cert_id":         cert_id,
        "cert_no":         doc.metadata.get("cert_no", ""),
        "company":         company,
        "product_name":    _extract_product_name(doc.raw_text),
        "pdf_path":        str(pdf_path),
        "attributes":      {
            k: {
                "is_present": v["is_present"],
                "value":      v.get("value"),
                "confidence": v.get("confidence", 0.0),
            }
            for k, v in attr_results.items()
        },
        "attr_vector":     attr_vector,
        "est_hrs":         est_hrs,
        "act_hrs":         act_hrs,
    }

    upsert_cert_job(job)

    # Summary
    present = [k for k, v in attr_results.items() if v["is_present"]]
    values  = {k: v["value"] for k, v in attr_results.items()
               if v["is_present"] and v.get("value")}

    result = {
        "cert_id":          cert_id,
        "cert_no":          doc.metadata.get("cert_no", ""),
        "company":          company,
        "pages":            doc.page_count,
        "attr_count":       len(present),
        "attr_total":       10,
        "attributes_found": present,
        "values_extracted": values,
        "attr_vector":      attr_vector,
        "est_hrs":          est_hrs,
        "act_hrs":          act_hrs,
        "variation":        round(act_hrs - est_hrs, 1),
    }

    logger.info(
        f"✅ {cert_id}: {len(present)}/10 attributes, "
        f"cert# {doc.metadata.get('cert_no','')}, "
        f"est={est_hrs}h act={act_hrs}h"
    )
    return result


def _extract_company(raw_text: str) -> str:
    """Better company name extraction from PDF text."""
    import re
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

    # Known company patterns in BBA certs
    company_patterns = [
        r"^([A-Z][a-zA-Z\s&\-\.]+(?:Ltd|Limited|plc|PLC|GmbH|Inc|BV|SAS)\.?)\s*$",
        r"^([A-Z][a-zA-Z\s&\-\.]+(?:Ltd|Limited|plc|PLC)\.?)",
    ]

    skip_patterns = [
        r"^page \d+", r"^bba", r"^tel", r"^fax", r"^www",
        r"agrément", r"technical approvals", r"approval.*inspection",
        r"^de\d+", r"^[a-z]{1,2}\d+", r"^\d+", r"^issue",
        r"^ps\d", r"certification", r"heanor", r"ipswich",
        r"suffolk", r"derbyshire", r"london", r"manchester",
    ]

    for line in lines[:30]:
        lower = line.lower()
        skip = any(re.search(p, lower) for p in skip_patterns)
        if skip:
            continue
        for pat in company_patterns:
            m = re.match(pat, line)
            if m and len(m.group(1)) > 5:
                return m.group(1).strip()

    # Fallback — look for line before a known address keyword
    for i, line in enumerate(lines[:25]):
        if re.search(r"\b(road|street|lane|avenue|gate|way|house)\b", line.lower()):
            if i > 0 and len(lines[i-1]) > 5:
                return lines[i-1].strip()

    return ""


def _extract_product_name(raw_text: str) -> str:
    """Extracts product name from cert text."""
    import re
    patterns = [
        r"(?:agrément certificate\s*\n+)(.+?)(?:\n|$)",
        r"(?:product name|system name|trade name)[:\s]+(.+?)(?:\n|$)",
        r"(?:for the use of\s+)(.+?)(?:\n|\.|$)",
    ]
    for pat in patterns:
        m = re.search(pat, raw_text, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            if 3 < len(name) < 100:
                return name
    return ""


def get_pipeline_summary(product_type_id: str = "LA") -> Dict[str, Any]:
    """Returns a summary of all ingested certs."""
    jobs = get_all_cert_jobs(product_type_id)
    if not jobs:
        return {"total": 0, "jobs": []}

    summary = []
    for j in jobs:
        attrs = j["attributes"]
        present = [k for k, v in attrs.items() if v.get("is_present")]
        summary.append({
            "cert_id":    j["cert_id"],
            "company":    j["company"],
            "cert_no":    j["cert_no"],
            "attr_count": len(present),
            "est_hrs":    j["est_hrs"],
            "act_hrs":    j["act_hrs"],
            "variation":  j["variation"],
        })

    return {
        "product_type":  product_type_id,
        "total":         len(jobs),
        "jobs":          summary,
        "avg_act_hrs":   round(sum(j["act_hrs"] for j in jobs) / len(jobs), 1),
        "avg_est_hrs":   round(sum(j["est_hrs"] for j in jobs) / len(jobs), 1),
    }