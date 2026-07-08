import json
import re
from typing import Dict, Any, List
from chatbot.llm_client import call_llm
from app.logger import get_logger
from app.config import settings

logger = get_logger("extractor_layer2")

# Only run Layer 2 on chunks above this technicality score
# Saves Groq API calls on low-value chunks
MIN_TECHNICALITY_FOR_L2 = 0.3

EXTRACTION_SYSTEM_PROMPT = """You are a technical data extraction engine for construction certification documents.

Your job is to extract structured information from technical text.

You MUST respond with ONLY a valid JSON object — no explanation, no markdown, no backticks.

Extract exactly these fields:
{
  "technical_entities": [],
  "functional_properties": [],
  "standards": [],
  "application_scope": [],
  "constraints": [],
  "performance_characteristics": [],
  "object_name": [],
  "product_name": []
}

Rules:
- technical_entities: materials, components, substrates mentioned (e.g. "polymer-modified render", "alkali-resistant mesh")
- functional_properties: what the product does (e.g. "fire resistance", "water repellency")
- standards: any standard or regulation codes (e.g. "BS EN 998-1 : 2016")
- application_scope: where/how the product is used (e.g. "external walls", "masonry substrates")
- constraints: limitations or requirements (e.g. "minimum 16mm thickness", "not suitable for horizontal surfaces")
- performance_characteristics: measurable values (e.g. "compressive strength 7 N/mm²")
- object_name: physical objects mentioned (e.g. "wall", "substrate", "render coat")
- product_name: specific product names (e.g. "K Rend K1 Spray")

If a field has nothing to extract return an empty list [].
Return ONLY the JSON object. Nothing else.
"""


def clean_json_response(response: str) -> str:
    """
    Cleans LLM response to extract valid JSON.
    Handles cases where the LLM adds extra text.
    """
    # Remove markdown code blocks if present
    response = re.sub(r"```(?:json)?", "", response)
    response = response.strip()

    # Find the first { and last } to extract JSON
    start = response.find("{")
    end = response.rfind("}") + 1

    if start == -1 or end == 0:
        return "{}"

    return response[start:end]


def extract_layer2(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs semantic extraction on a single chunk using Groq.
    Returns extracted metadata as a dict.
    """
    text = chunk.get("text", "")
    heading = chunk.get("heading", "")

    prompt_text = f"""Extract structured information from this construction certification text:

HEADING: {heading}

TEXT:
{text[:1500]}
"""

    try:
        response = call_llm(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_message=prompt_text,
            max_tokens=600,
            temperature=0.0,
        )

        clean = clean_json_response(response)
        extracted = json.loads(clean)

        # Ensure all expected fields exist
        expected_fields = [
            "technical_entities", "functional_properties",
            "standards", "application_scope", "constraints",
            "performance_characteristics", "object_name", "product_name"
        ]
        for field in expected_fields:
            if field not in extracted:
                extracted[field] = []
            if not isinstance(extracted[field], list):
                extracted[field] = [str(extracted[field])]

        return extracted

    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed for chunk {chunk.get('chunk_id')}: {e}")
        return {field: [] for field in [
            "technical_entities", "functional_properties",
            "standards", "application_scope", "constraints",
            "performance_characteristics", "object_name", "product_name"
        ]}

    except Exception as e:
        logger.error(f"Layer 2 extraction failed for chunk {chunk.get('chunk_id')}: {e}")
        return {field: [] for field in [
            "technical_entities", "functional_properties",
            "standards", "application_scope", "constraints",
            "performance_characteristics", "object_name", "product_name"
        ]}


def process_chunks_layer2(
    chunks: List[Dict[str, Any]],
    min_technicality: float = MIN_TECHNICALITY_FOR_L2,
) -> List[Dict[str, Any]]:
    """
    Runs Layer 2 semantic extraction on chunks.
    Only processes chunks above the technicality threshold.
    Skips low-value chunks to save Groq API calls.
    """
    eligible = [c for c in chunks if c.get("technicality_score", 0) >= min_technicality]
    skipped = len(chunks) - len(eligible)

    logger.info(
        f"Layer 2: {len(eligible)} chunks eligible "
        f"({skipped} skipped — below threshold {min_technicality})"
    )

    results = []
    for i, chunk in enumerate(chunks):
        if chunk.get("technicality_score", 0) >= min_technicality:
            logger.info(
                f"  Extracting chunk {i+1}/{len(chunks)}: "
                f"{chunk['chunk_id']} "
                f"(score: {chunk['technicality_score']})"
            )
            layer2_data = extract_layer2(chunk)
            chunk["layer2"] = layer2_data
        else:
            # Skip low-value chunks
            chunk["layer2"] = {field: [] for field in [
                "technical_entities", "functional_properties",
                "standards", "application_scope", "constraints",
                "performance_characteristics", "object_name", "product_name"
            ]}
        results.append(chunk)

    logger.info(f"✅ Layer 2 complete — {len(eligible)} chunks semantically extracted")
    return results