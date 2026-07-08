import re
from dataclasses import dataclass
from typing import Tuple

TECHNICAL  = "technical"
BUSINESS   = "business"
ESTIMATION = "estimation"
BI_QUERY   = "bi_query"
GREETING   = "greeting"
UNKNOWN    = "unknown"


@dataclass
class IntentResult:
    intent: str
    confidence: float
    reason: str
    bi_type: str = None  # for BI queries — which specific BI query


# ── KEYWORD LISTS ──────────────────────────────────────────────────────────

TECHNICAL_KEYWORDS = [
    "certificate", "certification", "cert", "compliance",
    "specification", "spec", "standard", "regulation",
    # NOTE: "render", "insulation", "roof", "temperature", "fire" removed —
    # these are common estimation product/answer words that caused follow-up
    # messages (e.g. "roof insulation", "250°C") to be misclassified as
    # TECHNICAL and routed to retrieval instead of the active estimation session.
    # The orchestrator's session-first routing is the primary guard; keeping
    # these out of TECHNICAL_KEYWORDS is a secondary safety net.
    "install", "installation",
    "blockwork", "concrete", "masonry", "substrate",
    "weathering", "moisture",
    "adhesion", "coating",
    "bs en", "nhbc", "building regulations",
    "bba", "certificate number",
    "thickness", "weight", "density", "strength",
    "performance",
    "compressive", "tensile", "flexural",
    "k rend", "k1", "spray", "polymer", "mesh",
    "manufacturer", "application",
    "how to", "how do", "what is the", "what are the",
    "requirements for", "suitable for", "used for",
    "compatible with", "approved for",
]

ESTIMATION_KEYWORDS = [
    "quote", "estimate", "quotation", "estimation",
    "how long", "how many hours", "effort", "scope",
    "we got a", "we have a", "new project",
    "project to quote", "similar jobs", "similar projects",
    "hours will", "hours for", "time for",
    "testing", "certification project", "job estimate",
    "predict", "prediction", "forecast hours",
    # KNN roofing specific
    "liquid applied", "liquid-applied", "roofing system",
    "waterproofing", "roof membrane", "flat roof",
    "roofing certificate", "roofing certification",
    "weathertight", "wind uplift", "root penetration",
]

# BI query keywords mapped to their specific BI type
BI_KEYWORD_MAP = {
    "customer_growth": [
        "growing customer", "declining customer", "customer growth",
        "customer decline", "yoy", "year on year", "churn",
        "at risk customer", "growth account", "which customers grew",
        "which customers declined", "stopped buying", "stopped purchasing",
        "growing or declining", "customers growing", "customers declining",
        "customer trend", "which customers", "customer analysis",
        "who is growing", "who is declining", "revenue trend",
        "highest sales growth", "last 12 months", "top customers stopped",
        "customers stopped", "recently stopped", "churn risk",
    ],
    "product_trends": [
        "product trend", "growing product", "fastest growing product",
        "product performance", "product decline", "which product",
        "product code", "best product", "product growing",
        "product declining", "product revenue",
    ],
    "job_type_intelligence": [
        "job type", "which sector", "sector trend", "hot sector",
        "job type revenue", "which job", "type of job",
        "sector performance", "job trend", "work stream trend",
        "most revenue", "generating revenue", "highest revenue job",
        "buy most frequently", "most frequent", "job frequency",
        "best job type", "growing job type",
    ],
    "salesperson_analysis": [
        "salesperson", "sales person", "sales rep", "rep performance",
        "who sells", "top salesperson", "best rep", "sales growth",
        "salesperson growth", "who brought", "new customer",
        "territory", "sp1", "sp2", "sp3", "sp4", "sp5",
        "grew accounts", "grew most", "salesperson grew",
        "who brought in", "new accounts", "depends heavily",
        "heavy dependency", "one customer", "single customer",
        "best salesperson", "top performer", "sales performance",
    ],
    "cross_sell": [
        "cross sell", "cross-sell", "expansion", "upsell",
        "buying one", "only one product", "potential",
        "work stream", "single stream", "narrow range",
        "opportunity", "cross selling",
    ],
    "target_achievement": [
        "target", "met target", "who meets", "who did not meet",
        "achievement", "quota", "hit target", "missed target",
        "performance target", "revenue target",
    ],
    "sales_summary": [
        "sales information", "total sales", "revenue for",
        "sales for", "how much did", "contract price",
        "sales between", "sales in", "invoice", "order value",
        "quarterly sales", "annual sales", "monthly sales",
        "financial year", "fy", "this year", "last year",
        "top customer", "top 5 customer", "best customer",
        "sales data", "revenue data", "show sales",
        "give me sales", "what are sales", "total revenue",
    ],
}

GREETING_KEYWORDS = [
    "hi", "hello", "hey", "good morning",
    "good afternoon", "good evening",
    "how are you", "what can you do",
    "help", "who are you", "what are you",
]


def classify_intent(query: str) -> IntentResult:
    """
    Classifies user query into one of 6 intent types:
    TECHNICAL, ESTIMATION, BI_QUERY, BUSINESS, GREETING, UNKNOWN
    """
    query_lower = query.lower().strip()

    # ── GREETING CHECK ─────────────────────────────────────────────────────
    for keyword in GREETING_KEYWORDS:
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, query_lower):
            return IntentResult(
                intent=GREETING,
                confidence=1.0,
                reason=f"Matched greeting keyword: '{keyword}'"
            )

    # ── ESTIMATION CHECK ───────────────────────────────────────────────────
    est_matches = [k for k in ESTIMATION_KEYWORDS if k in query_lower]
    if est_matches:
        return IntentResult(
            intent=ESTIMATION,
            confidence=1.0,
            reason=f"Matched estimation keywords: {est_matches[:3]}"
        )

    # ── BI QUERY CHECK ─────────────────────────────────────────────────────
    bi_scores = {}
    for bi_type, keywords in BI_KEYWORD_MAP.items():
        matches = [k for k in keywords if k in query_lower]
        if matches:
            bi_scores[bi_type] = (len(matches), matches)

    if bi_scores:
        best_bi = max(bi_scores, key=lambda k: bi_scores[k][0])
        count, matched = bi_scores[best_bi]
        return IntentResult(
            intent=BI_QUERY,
            confidence=min(1.0, count * 0.4),
            reason=f"Matched BI keywords: {matched[:3]}",
            bi_type=best_bi,
        )

    # ── TECHNICAL CHECK ────────────────────────────────────────────────────
    tech_matches = [k for k in TECHNICAL_KEYWORDS if k in query_lower]
    if tech_matches:
        return IntentResult(
            intent=TECHNICAL,
            confidence=min(1.0, len(tech_matches) * 0.25),
            reason=f"Matched technical keywords: {tech_matches[:3]}"
        )

    return IntentResult(
        intent=UNKNOWN,
        confidence=0.4,
        reason="No clear keywords matched — defaulting to technical search"
    )


def is_technical(query: str) -> bool:
    return classify_intent(query).intent in [TECHNICAL, UNKNOWN]

def is_business(query: str) -> bool:
    return classify_intent(query).intent in [BUSINESS, BI_QUERY]

def is_estimation(query: str) -> bool:
    return classify_intent(query).intent == ESTIMATION