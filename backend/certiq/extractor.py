"""
AI Attribute Extractor — Layer 3

Two-pass extraction:
Pass 1 — Regex: fast, free, finds keywords and extracts values
Pass 2 — Groq LLM: semantic understanding, fills gaps, extracts values

Returns for each attribute:
- is_present: True/False
- value: "25 years" / "Class B" / "2.0 kPa" / None
- confidence: 0.0 to 1.0
- evidence: the exact text snippet that triggered it
"""

import re
import json
from typing import Dict, Any, List
from certiq.parser import ParsedDocument
from certiq.store import get_attributes
from app.logger import get_logger

logger = get_logger("extractor")


def extract_pass1_regex(
    doc: ParsedDocument,
    attributes: List[Dict[str, Any]],
) -> Dict[str, Dict]:
    """
    Pass 1 — Deterministic regex extraction.
    For each attribute, searches keywords and tries to extract values.
    Returns dict: attr_name -> {is_present, value, confidence, evidence}
    """
    text = doc.text_lower
    results = {}

    for attr in attributes:
        attr_name = attr["attr_name"]
        keywords  = attr["search_keywords"]
        data_type = attr["data_type"]

        is_present = False
        value      = None
        confidence = 0.0
        evidence   = ""

        # Search for keywords
        for kw in keywords:
            matches = list(re.finditer(kw, text, re.IGNORECASE))
            if matches:
                is_present = True
                confidence = min(0.8, confidence + 0.2 * len(matches))
                # Get surrounding text as evidence
                m = matches[0]
                start = max(0, m.start() - 60)
                end   = min(len(text), m.end() + 80)
                evidence = doc.raw_text[start:end].replace("\n", " ").strip()
                break

        # Extract VALUES for numeric attributes
        if is_present and data_type == "numeric":
            value = _extract_numeric_value(text, attr_name, attr.get("unit", ""))

        # Extract text values for specific attributes
        if is_present and attr_name == "properties_in_relation_to_fire":
            value = _extract_fire_class(text)

        if is_present and attr_name == "durability":
            value = _extract_durability(text)

        if is_present and attr_name == "resistance_to_wind_uplift":
            value = _extract_wind_uplift(text)

        if is_present and attr_name == "adhesion":
            value = _extract_adhesion(text)

        results[attr_name] = {
            "is_present": is_present,
            "value":      value,
            "confidence": round(confidence, 2),
            "evidence":   evidence[:200],
            "source":     "regex",
        }

    return results


def _extract_numeric_value(text: str, attr_name: str, unit: str) -> str:
    """Extracts numeric values with units from text."""
    patterns = {
        "durability": [
            r"(\d+)\s*years?\s+(?:service life|design life|durability)",
            r"(?:service life|design life|at least)\s+(\d+)\s*years?",
            r"(\d+)\s*[-–]\s*year",
            r"expected\s+(?:to last|life)\s+(?:at least\s+)?(\d+)\s*years?",
        ],
        "resistance_to_wind_uplift": [
            r"(\d+(?:\.\d+)?)\s*kpa",
            r"wind\s+(?:uplift|load)\s+of\s+(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*kn/m",
        ],
        "adhesion": [
            r"(\d+(?:\.\d+)?)\s*n/mm",
            r"adhesion.*?(\d+(?:\.\d+)?)\s*(?:n/mm|mpa|kpa)",
            r"bond strength.*?(\d+(?:\.\d+)?)",
        ],
    }

    for pattern in patterns.get(attr_name, []):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            num = m.group(1)
            return f"{num} {unit}".strip() if unit else num

    return None


def _extract_fire_class(text: str) -> str:
    """Extracts fire classification from text."""
    patterns = [
        r"(broof\s*\([a-z0-9]+\))",
        r"(froof\s*\([a-z0-9]+\))",
        r"class\s+([a-f][0-9]?-[a-z][0-9]?)",
        r"euroclass\s+([a-f][0-9]?)",
        r"reaction\s+to\s+fire.*?class\s+([a-f])",
        r"(b-?roof|f-?roof)",
        r"(class\s+[a-f]\d?\s*,\s*[a-z]\d?)",
        r"fire.*?(class\s+[a-f]\d?)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).upper().strip()
    return "Present"


def _extract_durability(text: str) -> str:
    """Extracts durability/service life value."""
    patterns = [
        r"(\d+)\s*years?\s*(?:service life|design life|or more)",
        r"(?:service life|design life|at least)\s+(\d+)\s*years?",
        r"will\s+last\s+(?:at least\s+)?(\d+)\s*years?",
        r"(\d+)\s*[-–]\s*year\s+(?:design|service|expected)",
        r"expected\s+(?:service\s+)?life\s+of\s+(\d+)",
        r"minimum\s+(\d+)\s*years?",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return f"{m.group(1)} years"
    # Check for general year mentions near durability keywords
    dur_match = re.search(r"durabilit\w+[^.]*?(\d+)\s*years?", text, re.IGNORECASE)
    if dur_match:
        return f"{dur_match.group(1)} years"
    return "Confirmed"


def _extract_wind_uplift(text: str) -> str:
    """Extracts wind uplift values."""
    patterns = [
        r"(\d+(?:\.\d+)?)\s*kpa",
        r"wind\s+(?:uplift|load|suction)\s+(?:of\s+)?(\d+(?:\.\d+)?)",
        r"up\s+to\s+(\d+(?:\.\d+)?)\s*kpa",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return f"{m.group(1)} kPa"
    return "Confirmed"


def _extract_adhesion(text: str) -> str:
    """Extracts adhesion / bond strength values."""
    patterns = [
        r"(\d+(?:\.\d+)?)\s*n/mm[²2]?",
        r"(\d+(?:\.\d+)?)\s*mpa",
        r"bond strength\s+(?:of\s+)?(\d+(?:\.\d+)?)",
        r"adhesion\s+(?:strength\s+)?(?:of\s+)?(\d+(?:\.\d+)?)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return f"{m.group(1)} N/mm²"
    return "Confirmed"


def extract_pass2_llm(
    doc: ParsedDocument,
    attributes: List[Dict[str, Any]],
    pass1_results: Dict[str, Dict],
) -> Dict[str, Dict]:
    """
    Pass 2 — Groq LLM semantic extraction.
    Only runs on attributes where Pass 1 found low confidence
    or where value extraction failed.
    This saves API calls — only call LLM where needed.
    """
    # Find attributes that need LLM help
    needs_llm = []
    for attr in attributes:
        r = pass1_results.get(attr["attr_name"], {})
        if r.get("confidence", 0) < 0.5 or (r.get("is_present") and not r.get("value")):
            needs_llm.append(attr)

    if not needs_llm:
        logger.info("Pass 2 skipped — all attributes extracted with high confidence")
        return pass1_results

    logger.info(f"Pass 2 LLM — checking {len(needs_llm)} low-confidence attributes")

    # Build focused context — use sections most likely to contain technical data
    context_sections = []
    for section in doc.sections:
        heading = section.get("heading", "").lower()
        content = section.get("content", "")
        technical_headings = [
            "assessment", "technical", "performance", "properties",
            "installation", "durability", "fire", "wind", "adhesion",
            "weathertight", "regulations", "requirements", "scope",
        ]
        if any(h in heading for h in technical_headings):
            context_sections.append(f"{section['heading']}: {content[:300]}")

    # Fall back to raw text if no sections found
    if not context_sections:
        context_text = doc.raw_text[:3000]
    else:
        context_text = "\n\n".join(context_sections[:8])

    # Build attribute questions for LLM
    attr_list = []
    for attr in needs_llm:
        current = pass1_results.get(attr["attr_name"], {})
        attr_list.append(
            f"- {attr['display_name']}: is it present? "
            f"If yes, what is the value? (Current: {'found' if current.get('is_present') else 'not found'})"
        )

    system_prompt = """You are extracting technical attributes from construction certification documents.

For each attribute, determine:
1. Is it present in the document? (yes/no)
2. What is the specific value if mentioned? (e.g. "25 years", "Class B-s1,d0", "2.0 kPa")

Return ONLY a JSON object with this exact structure:
{
  "attribute_name_snake_case": {
    "is_present": true/false,
    "value": "extracted value or null",
    "evidence": "brief quote from document"
  }
}

Be precise. Only mark present if clearly stated. Extract actual values where given."""

    user_message = f"""Document text (relevant sections):
{context_text}

Attributes to check:
{chr(10).join(attr_list)}

Return JSON only."""

    try:
        from chatbot.llm_client import call_llm
        response = call_llm(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=800,
            temperature=0.0,
        )

        # Parse LLM response
        response = re.sub(r"```(?:json)?", "", response).strip()
        start = response.find("{")
        end   = response.rfind("}") + 1
        if start != -1 and end > 0:
            llm_results = json.loads(response[start:end])

            # Merge LLM results with Pass 1
            for attr in needs_llm:
                attr_name = attr["attr_name"]
                if attr_name in llm_results:
                    llm_r = llm_results[attr_name]
                    current = pass1_results.get(attr_name, {})

                    # LLM overrides if it found something Pass 1 missed
                    if llm_r.get("is_present") and not current.get("is_present"):
                        pass1_results[attr_name] = {
                            "is_present": True,
                            "value":      llm_r.get("value"),
                            "confidence": 0.7,
                            "evidence":   llm_r.get("evidence", "")[:200],
                            "source":     "llm",
                        }
                    # LLM fills in missing value
                    elif current.get("is_present") and not current.get("value"):
                        if llm_r.get("value"):
                            pass1_results[attr_name]["value"] = llm_r.get("value")
                            pass1_results[attr_name]["source"] = "regex+llm"

    except Exception as e:
        logger.warning(f"Pass 2 LLM failed: {e} — using Pass 1 results only")

    return pass1_results


def extract_attributes(
    doc: ParsedDocument,
    product_type_id: str = "LA",
    use_llm: bool = True,
) -> Dict[str, Dict]:
    """
    Main extraction function — runs both passes.

    Returns dict:
    {
      "weathertightness": {
        "is_present": True,
        "value": "Confirmed",
        "confidence": 0.8,
        "evidence": "...text snippet...",
        "source": "regex"
      },
      ...
    }
    """
    attributes = get_attributes(product_type_id)

    logger.info(f"Extracting {len(attributes)} attributes from {doc.metadata['filename']}")

    # Pass 1 — regex
    results = extract_pass1_regex(doc, attributes)

    present = sum(1 for r in results.values() if r["is_present"])
    logger.info(f"Pass 1 found {present}/{len(attributes)} attributes")

    # Pass 2 — LLM for low-confidence ones
    if use_llm:
        results = extract_pass2_llm(doc, attributes, results)
        present = sum(1 for r in results.values() if r["is_present"])
        logger.info(f"After Pass 2: {present}/{len(attributes)} attributes")

    return results


def build_attr_vector(
    extraction_results: Dict[str, Dict],
    product_type_id: str = "LA",
) -> List[float]:
    """
    Converts extraction results into a numeric vector for KNN.
    Boolean: 0.0 (absent) or 1.0 (present)
    Numeric: normalised 0.0-1.0, or 0.8 if present but no value extracted
    """
    attributes = get_attributes(product_type_id)
    vector = []

    for attr in attributes:
        name       = attr["attr_name"]
        result     = extraction_results.get(name, {})
        is_present = result.get("is_present", False)

        if not is_present:
            vector.append(0.0)
            continue

        if attr["data_type"] == "boolean":
            vector.append(1.0)
        elif attr["data_type"] == "numeric":
            val_str = str(result.get("value", ""))
            nums    = re.findall(r"\d+(?:\.\d+)?", val_str)
            if nums:
                val = float(nums[0])
                if "durability" in name:
                    vector.append(min(val / 50.0, 1.0))   # 50 years = 1.0
                elif "wind" in name:
                    vector.append(min(val / 5.0, 1.0))    # 5 kPa = 1.0
                else:
                    vector.append(min(val / 100.0, 1.0))
            else:
                vector.append(0.8)  # present but no numeric value — high, not perfect
        else:
            vector.append(1.0)

    return vector