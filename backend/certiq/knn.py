"""
KNN Inference Engine with Gower Distance

Why Gower distance?
- Standard Euclidean distance only works for numeric data
- Our attributes are MIXED: boolean (yes/no) + numeric (25 years, 2.0 kPa)
- Gower distance handles both correctly:
  - Boolean: distance = 0 if same, 1 if different
  - Numeric: distance = |a - b| / range(attribute)
- This is exactly what the boss's diagram specifies

The model is NOT retrained when new certs are added.
KNN is instance-based — it just stores and compares.
This is a key advantage over Random Forest for small datasets.
"""

import json
import math
from typing import List, Dict, Any, Optional, Tuple
from certiq.store import (
    get_all_cert_jobs, get_attributes,
    log_inference, DB_PATH,
)
from app.logger import get_logger

logger = get_logger("knn")


def gower_distance(
    vec_a: List[float],
    vec_b: List[float],
    weights: List[float],
    data_types: List[str],
    ranges: List[float],
    cert_presence: List[float] = None,
) -> float:
    """
    Computes weighted Gower distance.
    Only compares dimensions where the CERT has the attribute.
    This prevents penalising the user for requesting more attributes
    than a cert was tested for.

    For boolean attributes: distance = 0 if same, 1 if different
    For numeric attributes: distance = |a - b| / range

    When user has an attribute the cert does not (cert_presence[i] == 0):
    - applies a small partial penalty (0.3) instead of full penalty (1.0)

    Returns value between 0.0 (identical) and 1.0 (completely different).
    """
    if len(vec_a) != len(vec_b):
        raise ValueError(f"Vector length mismatch: {len(vec_a)} vs {len(vec_b)}")

    total_weight  = 0.0
    weighted_dist = 0.0

    for i, (a, b) in enumerate(zip(vec_a, vec_b)):
        w     = weights[i] if i < len(weights) else 1.0
        dtype = data_types[i] if i < len(data_types) else "boolean"
        r     = ranges[i] if i < len(ranges) else 1.0

        # Skip dimensions where cert has 0 (not tested / not present)
        # Only compare where cert actually has the attribute
        if cert_presence and cert_presence[i] == 0.0 and a > 0:
            # User wants this but cert does not have it — partial penalty
            weighted_dist += w * 0.3  # small penalty, not full penalty
            total_weight  += w
            continue

        if dtype == "boolean":
            d = 0.0 if a == b else 1.0
        else:
            d = abs(a - b) / r if r > 0 else (0.0 if a == b else 1.0)

        weighted_dist += w * d
        total_weight  += w

    return round(weighted_dist / total_weight, 4) if total_weight > 0 else 1.0


def build_gower_params(product_type_id: str = "LA") -> Tuple[List, List, List]:
    """
    Builds the weights, data_types, and ranges needed for Gower distance.
    These are derived from the attribute definitions in the KNN store.
    """
    attributes = get_attributes(product_type_id)

    weights    = [attr["weight"]    for attr in attributes]
    data_types = [attr["data_type"] for attr in attributes]

    # Ranges for numeric normalisation
    # Boolean: range = 1.0 (always)
    # Numeric: range = max expected value for that attribute
    ranges = []
    for attr in attributes:
        if attr["data_type"] == "numeric":
            if "durability" in attr["attr_name"]:
                ranges.append(1.0)   # already normalised 0-1
            elif "wind" in attr["attr_name"]:
                ranges.append(1.0)   # already normalised 0-1
            else:
                ranges.append(1.0)
        else:
            ranges.append(1.0)

    return weights, data_types, ranges


def run_knn_inference(
    query_vector: List[float],
    product_type_id: str = "LA",
    k: int = 3,
    session_id: str = "",
    input_attributes: Dict = None,
    input_source: str = "chatbot",
) -> Dict[str, Any]:
    """
    Main KNN inference function.

    Given a query vector (from a new document or user form),
    finds the K nearest certs by Gower distance and
    predicts effort hours.

    Returns:
    - predicted_hrs: effort estimate
    - confidence: HIGH/MEDIUM/LOW
    - k_neighbors: the K most similar certs with distances
    - match_explanation: human readable explanation
    """
    # Load all stored cert jobs
    cert_jobs = get_all_cert_jobs(product_type_id)

    if not cert_jobs:
        return {
            "error": "No certs in KNN store. Run the offline pipeline first.",
            "predicted_hrs": 40.0,
            "confidence": "LOW",
        }

    # Build Gower parameters
    weights, data_types, ranges = build_gower_params(product_type_id)

    # Calculate distance to every cert
    distances = []
    for job in cert_jobs:
        cert_vector = job["attr_vector"]
        if not cert_vector or len(cert_vector) != len(query_vector):
            logger.warning(f"Skipping {job['cert_id']} — vector mismatch")
            continue

        dist = gower_distance(
            query_vector, cert_vector,
            weights, data_types, ranges,
            cert_presence=cert_vector,  # pass cert vector as presence mask
        )

        # Convert distance to similarity percentage
        similarity_pct = round((1 - dist) * 100, 1)

        distances.append({
            "cert_id":      job["cert_id"],
            "company":      job["company"],
            "cert_no":      job["cert_no"],
            "distance":     dist,
            "similarity":   similarity_pct,
            "est_hrs":      job["est_hrs"],
            "act_hrs":      job["act_hrs"],
            "variation":    job["variation"],
            "attr_vector":  cert_vector,
            "attributes":   job["attributes"],
        })

    # Sort by distance (closest first)
    distances.sort(key=lambda x: x["distance"])

    # Take top K neighbors
    k = min(k, len(distances))
    neighbors = distances[:k]

    if not neighbors:
        return {
            "error": "No neighbors found",
            "predicted_hrs": 40.0,
            "confidence": "LOW",
        }

    # ── PREDICTION: weighted average of K neighbors' actual hours ──────────
    # Closer neighbors get higher weight (inverse distance weighting)
    total_weight = 0.0
    weighted_hrs = 0.0

    for n in neighbors:
        # Avoid division by zero for perfect matches
        weight = 1.0 / (n["distance"] + 0.0001)
        weighted_hrs += weight * n["act_hrs"]
        total_weight += weight

    predicted_hrs = round(weighted_hrs / total_weight, 1) if total_weight > 0 else neighbors[0]["act_hrs"]

    # ── CONFIDENCE based on best match similarity ──────────────────────────
    best_similarity = neighbors[0]["similarity"]
    if best_similarity >= 80:
        confidence = "HIGH"
    elif best_similarity >= 50:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # ── BUILD EXPLANATION ──────────────────────────────────────────────────
    best = neighbors[0]
    explanation_lines = [
        f"Best match: **{best['cert_id']}** ({best['company']}) "
        f"at **{best['similarity']}% similarity**",
        f"Predicted effort: **{predicted_hrs} hrs** "
        f"(weighted average of {k} nearest certs)",
    ]

    if best["variation"] > 0:
        explanation_lines.append(
            f"Note: {best['cert_id']} historically ran "
            f"**{best['variation']:+.1f} hrs over estimate** — "
            f"consider padding your quote"
        )
    elif best["variation"] < 0:
        explanation_lines.append(
            f"Note: {best['cert_id']} historically came in "
            f"**{abs(best['variation']):.1f} hrs under estimate**"
        )

    # ── LOG INFERENCE ──────────────────────────────────────────────────────
    log_inference({
        "session_id":       session_id,
        "product_type_id":  product_type_id,
        "input_attributes": input_attributes or {},
        "input_source":     input_source,
        "k_neighbors":      k,
        "matched_jobs":     [
            {
                "cert_id":    n["cert_id"],
                "similarity": n["similarity"],
                "act_hrs":    n["act_hrs"],
            }
            for n in neighbors
        ],
        "predicted_hrs":    predicted_hrs,
        "confidence":       confidence,
    })

    return {
        "predicted_hrs":   predicted_hrs,
        "confidence":      confidence,
        "best_similarity": best_similarity,
        "k_neighbors":     neighbors,
        "explanation":     "\n".join(explanation_lines),
        "product_type_id": product_type_id,
    }


def run_knn_on_pdf(
    pdf_path: str,
    product_type_id: str = "LA",
    k: int = 3,
    use_llm: bool = False,
    session_id: str = "",
) -> Dict[str, Any]:
    """
    Full pipeline for a new test PDF:
    1. Parse PDF
    2. Extract attributes
    3. Build query vector
    4. Run KNN inference
    5. Return prediction + match details
    """
    from certiq.parser import parse_any
    from certiq.extractor import extract_attributes, build_attr_vector

    # Parse and extract
    doc          = parse_any(pdf_path)
    attr_results = extract_attributes(doc, product_type_id, use_llm)
    query_vector = build_attr_vector(attr_results, product_type_id)

    # Run KNN
    result = run_knn_inference(
        query_vector=query_vector,
        product_type_id=product_type_id,
        k=k,
        session_id=session_id,
        input_attributes={
            k: v for k, v in attr_results.items() if v["is_present"]
        },
        input_source="pdf",
    )

    # Add attribute extraction details to result
    result["extracted_attributes"] = attr_results
    result["query_vector"]         = query_vector
    result["source_file"]          = pdf_path
    result["cert_no"]              = doc.metadata.get("cert_no", "")
    result["company"]              = doc.metadata.get("company", "")

    return result


def format_knn_result(result: Dict[str, Any]) -> str:
    """Formats KNN result as markdown for the chatbot."""
    if "error" in result:
        return f"❌ {result['error']}"

    lines = [
        "## 🔍 KNN Similarity Match — Roofing (liquid-applied)\n",
        f"**Predicted Effort: {result['predicted_hrs']} hrs** "
        f"({'✅ HIGH' if result['confidence']=='HIGH' else '⚠️ MEDIUM' if result['confidence']=='MEDIUM' else '❓ LOW'} confidence)\n",
        f"_{result['explanation']}_\n",
        "\n### Top Matches\n",
        "| Cert | Company | Similarity | Act Hrs | Variation |",
        "|------|---------|------------|---------|-----------|",
    ]

    for n in result["k_neighbors"]:
        bar      = "█" * int(n["similarity"] / 10)
        var_str  = f"{n['variation']:+.1f}h"
        var_flag = "🔴" if n["variation"] > 5 else "🟢" if n["variation"] < -5 else "🟡"
        lines.append(
            f"| {n['cert_id']} "
            f"| {n['company'][:25]} "
            f"| {n['similarity']}% {bar} "
            f"| {n['act_hrs']} hrs "
            f"| {var_flag} {var_str} |"
        )

    # Show attribute breakdown if available
    if result.get("extracted_attributes"):
        attrs   = result["extracted_attributes"]
        present = [k for k, v in attrs.items() if v["is_present"]]
        values  = {k: v["value"] for k, v in attrs.items()
                   if v["is_present"] and v.get("value")
                   and v["value"] not in ["Confirmed", "Present"]}

        lines.append(f"\n**Attributes found in document: {len(present)}/10**")
        if values:
            lines.append("\n**Extracted values:**")
            for k, v in values.items():
                display = k.replace("_", " ").title()
                lines.append(f"- {display}: **{v}**")

    return "\n".join(lines)