"""
Dynamic Form API — Live Inference Pipeline

When a user requests an estimate, this generates the exact
form fields to show them based on the product type's attribute registry.

The form changes automatically when:
- New attributes are added to the registry
- New product types are registered
- Attribute weights or requirements change

This matches the boss's diagram: Chatbot → Intent Detection → Dynamic Form
"""

from typing import List, Dict, Any, Optional
from certiq.store import get_attributes, get_all_cert_jobs, DB_PATH
from certiq.knn import run_knn_inference, build_gower_params
from certiq.extractor import build_attr_vector
from app.logger import get_logger
import re

logger = get_logger("forms")


def get_dynamic_form(product_type_id: str = "LA") -> Dict[str, Any]:
    """
    Returns the dynamic form definition for a product type.
    The frontend uses this to render the correct input fields.

    Each field has:
    - attr_id: unique identifier
    - attr_name: snake_case name
    - display_name: human readable label
    - field_type: boolean/number/text/select
    - question: what to ask the user
    - hint: example values
    - is_required: whether user must fill this
    - weight: importance for matching
    """
    attributes = get_attributes(product_type_id)

    if not attributes:
        return {"error": f"No attributes found for product type: {product_type_id}"}

    fields = []
    for attr in attributes:
        field = {
            "attr_id":      attr["attr_id"],
            "attr_name":    attr["attr_name"],
            "display_name": attr["display_name"],
            "question":     attr["form_question"],
            "hint":         attr["form_hint"] or "",
            "is_required":  bool(attr["is_required"]),
            "weight":       attr["weight"],
        }

        # Map data_type to form field type
        if attr["data_type"] == "boolean":
            field["field_type"] = "boolean"
            field["options"]    = ["Yes", "No"]
        elif attr["data_type"] == "numeric":
            field["field_type"] = "number"
            field["unit"]       = attr.get("unit", "")
        else:
            field["field_type"] = "text"

        fields.append(field)

    # Split into required and optional
    required = [f for f in fields if f["is_required"]]
    optional = [f for f in fields if not f["is_required"]]

    return {
        "product_type_id": product_type_id,
        "total_fields":    len(fields),
        "required_count":  len(required),
        "optional_count":  len(optional),
        "required_fields": required,
        "optional_fields": optional,
        "all_fields":      fields,
    }


def parse_form_submission(
    form_data: Dict[str, Any],
    product_type_id: str = "LA",
) -> Dict[str, Dict]:
    """
    Converts a submitted form into the attribute results format
    that the KNN engine expects.

    Form data example:
    {
      "weathertightness": "Yes",
      "durability": "25",
      "properties_in_relation_to_fire": "Yes",
      ...
    }

    Returns:
    {
      "weathertightness": {"is_present": True, "value": None, "confidence": 1.0},
      "durability": {"is_present": True, "value": "25 years", "confidence": 1.0},
      ...
    }
    """
    attributes  = get_attributes(product_type_id)
    attr_lookup = {a["attr_name"]: a for a in attributes}
    results     = {}

    for attr in attributes:
        attr_name = attr["attr_name"]
        raw_value = form_data.get(attr_name, form_data.get(attr["display_name"], ""))

        if not raw_value:
            results[attr_name] = {
                "is_present": False,
                "value":      None,
                "confidence": 1.0,
                "source":     "form",
            }
            continue

        raw_str = str(raw_value).strip().lower()

        if attr["data_type"] == "boolean":
            is_present = raw_str in ["yes", "true", "1", "y", "✓", "x"]
            results[attr_name] = {
                "is_present": is_present,
                "value":      None,
                "confidence": 1.0,
                "source":     "form",
            }

        elif attr["data_type"] == "numeric":
            nums = re.findall(r"\d+(?:\.\d+)?", str(raw_value))
            if nums:
                unit = attr.get("unit", "")
                results[attr_name] = {
                    "is_present": True,
                    "value":      f"{nums[0]} {unit}".strip(),
                    "confidence": 1.0,
                    "source":     "form",
                }
            else:
                results[attr_name] = {
                    "is_present": False,
                    "value":      None,
                    "confidence": 1.0,
                    "source":     "form",
                }
        else:
            is_present = bool(raw_value) and raw_str not in ["no", "none", "n/a", ""]
            results[attr_name] = {
                "is_present": is_present,
                "value":      str(raw_value) if is_present else None,
                "confidence": 1.0,
                "source":     "form",
            }

    return results


def run_inference_from_form(
    form_data: Dict[str, Any],
    product_type_id: str = "LA",
    k: int = 3,
    session_id: str = "",
) -> Dict[str, Any]:
    """
    Full live inference pipeline from form submission:
    1. Parse form data into attribute results
    2. Build query vector
    3. Run KNN
    4. Return prediction + similar jobs

    This is the path: Dynamic Form → Estimation Engine → Cost Estimate
    """
    attr_results = parse_form_submission(form_data, product_type_id)
    query_vector = build_attr_vector(attr_results, product_type_id)

    result = run_knn_inference(
        query_vector=query_vector,
        product_type_id=product_type_id,
        k=k,
        session_id=session_id,
        input_attributes=form_data,
        input_source="form",
    )

    result["extracted_attributes"] = attr_results
    result["query_vector"]         = query_vector
    result["form_data"]            = form_data
    return result


def run_inference_from_text(
    text: str,
    product_type_id: str = "LA",
    k: int = 3,
    session_id: str = "",
) -> Dict[str, Any]:
    """
    Live inference from plain text — email, chatbot message, etc.
    Parses text, extracts attributes, runs KNN.
    """
    from certiq.parser import parse_any
    from certiq.extractor import extract_attributes

    doc          = parse_any(text)
    attr_results = extract_attributes(doc, product_type_id, use_llm=False)
    query_vector = build_attr_vector(attr_results, product_type_id)

    result = run_knn_inference(
        query_vector=query_vector,
        product_type_id=product_type_id,
        k=k,
        session_id=session_id,
        input_attributes={
            k: v for k, v in attr_results.items() if v["is_present"]
        },
        input_source="text",
    )

    result["extracted_attributes"] = attr_results
    result["query_vector"]         = query_vector
    return result


def format_form_result(result: Dict[str, Any]) -> str:
    """Formats form inference result as markdown for chatbot."""
    if "error" in result:
        return f"❌ {result['error']}"

    conf_emoji = {
        "HIGH":   "✅",
        "MEDIUM": "⚠️",
        "LOW":    "❓",
    }.get(result["confidence"], "❓")

    lines = [
        "## 📋 Estimation Result — Roofing (liquid-applied)\n",
        f"### {conf_emoji} Predicted Effort: **{result['predicted_hrs']} hrs**\n",
        f"_{result.get('explanation', '')}_\n",
        "\n### Similar Historical Jobs\n",
        "| Cert | Company | Similarity | Act Hrs | Variation |",
        "|------|---------|------------|---------|-----------|",
    ]

    for n in result.get("k_neighbors", []):
        var_flag = "🔴" if n["variation"] > 5 else "🟢" if n["variation"] < -5 else "🟡"
        lines.append(
            f"| {n['cert_id']} "
            f"| {n['company'][:22]} "
            f"| {n['similarity']}% "
            f"| {n['act_hrs']} hrs "
            f"| {var_flag} {n['variation']:+.1f}h |"
        )

    # Show what attributes user provided
    attrs = result.get("extracted_attributes", {})
    present = [k.replace("_", " ").title()
               for k, v in attrs.items() if v.get("is_present")]
    if present:
        lines.append(f"\n**Attributes provided:** {', '.join(present)}")

    values = {
        k.replace("_", " ").title(): v["value"]
        for k, v in attrs.items()
        if v.get("is_present") and v.get("value")
        and v["value"] not in ["Confirmed", "Present"]
    }
    if values:
        lines.append("\n**Extracted values:**")
        for k, v in values.items():
            lines.append(f"- {k}: **{v}**")

    return "\n".join(lines)