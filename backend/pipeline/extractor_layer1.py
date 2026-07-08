import re
from typing import Dict, Any, List
from app.logger import get_logger

logger = get_logger("extractor_layer1")


# ── REGEX PATTERNS ─────────────────────────────────────────────────────────
# Each pattern targets a specific field found in certification documents

PATTERNS = {

    # Certificate numbers — e.g. BBA 21/5876, BBA Certificate 19/5612
    "cert_no": [
        r"BBA\s+(?:Certificate\s+)?(?:No\.?\s*)?(\d{2}/\d{4,5})",
        r"Certificate\s+(?:No\.?\s*)?([A-Z0-9]{4,}-[A-Z0-9]{2,}-[A-Z0-9]+)",
        r"Cert(?:ificate)?\s+(?:No\.?\s*)?([A-Z0-9/-]{6,})",
    ],

    # Job numbers
    "job_no": [
        r"Job\s+(?:No\.?\s*)?([A-Z0-9/-]{4,})",
        r"Project\s+(?:No\.?\s*)?([A-Z0-9/-]{4,})",
        r"Ref(?:erence)?\s+(?:No\.?\s*)?([A-Z0-9/-]{4,})",
    ],

    # Document types
    "document_type": [
        r"(BBA Certificate)",
        r"(Technical\s+Specification)",
        r"(Fire\s+Resistance\s+Report)",
        r"(Compliance\s+Certificate)",
        r"(Test\s+Report)",
        r"(Installation\s+Guide)",
        r"(Product\s+Data\s+Sheet)",
    ],

    # Company names
    "company": [
        r"(?:manufactured|supplied|produced)\s+by\s+([A-Z][A-Za-z\s&]+(?:Ltd|Limited|plc|PLC|Inc))",
        r"([A-Z][A-Za-z\s&]+(?:Ltd|Limited|plc|PLC))\s+(?:is|are|has)",
    ],

    # Product labels
    "product_label": [
        r"(?:product|system|material)\s+(?:is\s+)?(?:known\s+as\s+)?[\"']?([A-Z][A-Za-z0-9\s\-]+)[\"']",
        r"([A-Z][A-Za-z0-9\s\-]+)\s+(?:render|system|product|coating|insulation)",
    ],

    # Dates
    "dates": [
        r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})",
        r"(\d{4}[-/]\d{2}[-/]\d{2})",
        r"(?:issued|published|dated|valid\s+until|expiry)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    ],

    # Standards — BS EN, ISO, NHBC etc.
    "standards": [
        r"(BS\s+EN\s+\d+(?:[:-]\d+)?(?:\s*:\s*\d{4})?)",
        r"(BS\s+\d+(?:[:-]\d+)?(?:\s*:\s*\d{4})?)",
        r"(ISO\s+\d+(?:[:-]\d+)?(?:\s*:\s*\d{4})?)",
        r"(EN\s+\d+(?:[:-]\d+)?(?:\s*:\s*\d{4})?)",
        r"(NHBC\s+Standards?\s+\d{4})",
        r"(Building\s+Regulations?\s+\d{4})",
        r"(Regulation\s+\d+[a-z]?(?:\(\d+\))?)",
    ],

    # Dimensions — thickness, width, height
    "dimensions": [
        r"(\d+(?:\.\d+)?\s*(?:mm|cm|m))\s*(?:thick|thickness|wide|width|high|height|long|length)",
        r"(?:thick|thickness|wide|width)\s+(?:of\s+)?(\d+(?:\.\d+)?\s*(?:mm|cm|m))",
        r"(\d+(?:\.\d+)?)\s*(?:to|–|-)\s*(\d+(?:\.\d+)?)\s*mm",
    ],

    # Temperatures
    "temperatures": [
        r"(\d+(?:\.\d+)?)\s*°\s*[CF]",
        r"(\d+(?:\.\d+)?)\s*degrees?\s+(?:Celsius|Fahrenheit|centigrade)",
        r"(?:temperature|temp)\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*°",
    ],

    # Weight/density values
    "weights": [
        r"(\d+(?:\.\d+)?)\s*(?:kg[·•]?m[-–]?\d|kg/m[²³]?)",
        r"(\d+(?:\.\d+)?)\s*(?:g[·•]?m[-–]?\d|g/m[²³]?)",
        r"(?:weight|density|mass)\s+(?:of\s+)?(\d+(?:\.\d+)?)",
    ],

    # Regulation references
    "regulation_refs": [
        r"(Regulation\s+\d+[a-zA-Z]?(?:\s*\(\d+\))?(?:\s*\([a-z]\))?)",
        r"(Part\s+[A-Z]\s+of\s+the\s+Building\s+Regulations?)",
        r"(Schedule\s+\d+)",
        r"(Approved\s+Document\s+[A-Z]\d?)",
    ],
}


def extract_layer1(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs deterministic regex extraction on a single chunk.
    Returns a dict of extracted fields.
    Fast and free — no LLM needed.
    """
    text = chunk.get("text", "")
    heading = chunk.get("heading", "")
    full_text = heading + "\n" + text

    extracted = {
        "cert_no": [],
        "job_no": [],
        "document_type": [],
        "company": [],
        "product_label": [],
        "dates": [],
        "standards": [],
        "dimensions": [],
        "temperatures": [],
        "weights": [],
        "regulation_refs": [],
    }

    for field, patterns in PATTERNS.items():
        matches = set()
        for pattern in patterns:
            found = re.findall(pattern, full_text, re.IGNORECASE | re.MULTILINE)
            for match in found:
                if isinstance(match, tuple):
                    # Some patterns have groups — take the first non-empty
                    match = next((m for m in match if m), "")
                match = match.strip()
                if match and len(match) > 2:
                    matches.add(match)
        extracted[field] = sorted(list(matches))

    return extracted


def compute_technicality_score(chunk: Dict[str, Any], extracted: Dict[str, Any]) -> float:
    """
    Computes a technicality score between 0.0 and 1.0.
    Higher score = more technical content.
    Based on how many structured fields were extracted.
    """
    score = 0.0
    weights = {
        "standards": 0.25,
        "dimensions": 0.20,
        "temperatures": 0.15,
        "weights": 0.15,
        "regulation_refs": 0.15,
        "cert_no": 0.10,
    }

    for field, weight in weights.items():
        if extracted.get(field):
            score += weight

    # Also boost score based on technical keywords in text
    text = chunk.get("text", "").lower()
    technical_terms = [
        "compressive", "tensile", "flexural", "resistance",
        "permeability", "absorption", "adhesion", "density",
        "thermal", "conductivity", "reaction to fire",
    ]
    keyword_hits = sum(1 for term in technical_terms if term in text)
    score += min(0.20, keyword_hits * 0.02)

    return round(min(1.0, score), 3)


def process_chunks_layer1(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Runs Layer 1 extraction on all chunks.
    Adds extracted fields and technicality score to each chunk.
    """
    logger.info(f"Running Layer 1 extraction on {len(chunks)} chunks...")
    results = []

    for chunk in chunks:
        extracted = extract_layer1(chunk)
        tech_score = compute_technicality_score(chunk, extracted)

        enriched = {
            **chunk,
            "layer1": extracted,
            "technicality_score": tech_score,
        }
        results.append(enriched)

    logger.info(f"✅ Layer 1 complete — {len(results)} chunks processed")
    return results