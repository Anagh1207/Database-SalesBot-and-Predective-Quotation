import logging
import json
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)


def classify_intent_with_openrouter(query: str) -> str:
    """
    Classifies the user query using OpenRouter to route it to:
    - 'sales_analytics' (for PostgreSQL SQL queries, dashboard summaries, top customers, salesperson target performance, etc.)
    - 'construction_ai' (for plasterboard, waterproofing, technical specifications, BBA certificates, effort hours estimation, KNN liquid applied roofing, building regulations)

    Returns 'sales_analytics' or 'construction_ai'. Defaults to 'sales_analytics' on failure/fallback.
    """
    if not settings.openrouter_api_key:
        logger.warning("OPENROUTER_API_KEY not set, defaulting to sales_analytics")
        return "sales_analytics"

    try:
        client = OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
        )

        prompt = f"""You are a query router for an enterprise chatbot system. Route the user query to exactly one of three categories.

CATEGORY 1 — "sales_lookup":
Simple greetings or fixed-template sales lookups that map directly to pre-built reports.
Examples:
- "hi", "hello", "what can you do"
- "total sales this year"
- "top 5 customers this quarter"
- "who met their target?"
- "sales for Mike Johnson in Q1 2025"

CATEGORY 2 — "sales_text_to_sql":
Any sales question that needs custom SQL reasoning — rankings, comparisons, best/worst, trends, growth/decline, aggregations across segments, or any question that cannot be answered by a fixed report template.
Examples:
- "who is the best salesperson in terms of sales" (ranking)
- "who is the top performing rep" (ranking)
- "compare cladding-only customers vs insulation customers" (comparison)
- "which product codes grew fastest this year" (trend)
- "what job types buy most frequently" (frequency aggregation)
- "which customers stopped buying recently" (churn)
- "show me sales by region and product type" (custom grouping)
- "which salesperson has the most customers" (complex aggregation)
- "what is the revenue split between work streams" (segment analysis)
Key signal: words like best, top, worst, compare, vs, grow, decline, trend, fastest, most, least, breakdown, split, rank, which, who.

CATEGORY 3 — "construction_ai":
Technical specifications, building compliance, BBA certificates, material properties, regulations (BS EN, NHBC), or project effort estimation for construction jobs (plasterboard, cladding, roofing membranes, liquid-applied waterproofing, etc.).
Examples:
- "what is the flexural strength of plasterboard?"
- "does K-Rend have BBA certification?"
- "we need to quote for a liquid-applied roofing project"
- "estimate hours for fire testing 300 sqm flat roof"

Query: "{query}"

Analyze the query carefully. If it involves any ranking, comparison, or custom aggregation of sales data, choose sales_text_to_sql.
Return ONLY a valid JSON object (no markdown, no backticks):
{{
  "category": "sales_lookup" | "sales_text_to_sql" | "construction_ai",
  "reason": "one sentence explanation"
}}
"""

        response = client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        
        # Clean any accidental markdown wrap
        if content.startswith("```"):
            content = content.split("json")[-1].split("```")[0].strip()

        data = json.loads(content)
        category = data.get("category", "sales_lookup")
        if category in ["sales_lookup", "sales_text_to_sql", "construction_ai"]:
            logger.info(f"OpenRouter routed query '{query[:40]}' to -> {category} (reason: {data.get('reason')})")
            return category
    except Exception as e:
        logger.error(f"OpenRouter classification failed: {e}. Defaulting to sales_lookup.")

    return "sales_lookup"
