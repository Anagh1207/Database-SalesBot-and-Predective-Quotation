import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from chatbot.intent_classifier import (
    classify_intent, TECHNICAL, BUSINESS,
    GREETING, UNKNOWN, ESTIMATION, BI_QUERY
)
from chatbot.prompt_builder import build_prompt
from chatbot.llm_client import call_llm
from chatbot.estimation_flow import handle_estimation_message, is_estimation_query
from retrieval.search import search
from app.logger import get_logger
from app.config import settings
from certiq.chatbot_bridge import (
    handle_knn_message, is_knn_session_active,
    clear_knn_session, _knn_sessions,
)

logger = get_logger("orchestrator")


@dataclass
class ChatResponse:
    answer: str
    intent: str
    confidence: float
    sources: List[Dict[str, Any]]
    total_chunks_searched: int
    response_time: float
    model_used: str
    jobs: List[Dict[str, Any]] = field(default_factory=list)
    jobs_table: str = ""
    is_estimation: bool = False
    bi_data: Optional[Dict[str, Any]] = None
    prediction: Optional[Dict[str, Any]] = None


# ── BI QUERY HANDLER ───────────────────────────────────────────────────────

def handle_bi_query(query: str, bi_type: str) -> ChatResponse:
    start = time.time()
    logger.info(f"BI query type: {bi_type} | query: '{query[:60]}'")

    try:
        from predictor.bi_engine import (
            customer_growth, product_trends, job_type_intelligence,
            salesperson_analysis, cross_sell_opportunities,
            target_achievement, sales_summary,
        )

        if bi_type == "customer_growth":
            data = customer_growth(top_n=10)
            answer = _format_customer_growth(data, query)

        elif bi_type == "product_trends":
            data = product_trends(top_n=15)
            answer = _format_product_trends(data, query)

        elif bi_type == "job_type_intelligence":
            data = job_type_intelligence()
            answer = _format_job_type_intelligence(data, query)

        elif bi_type == "salesperson_analysis":
            data = salesperson_analysis()
            answer = _format_salesperson_analysis(data, query)

        elif bi_type == "cross_sell":
            data = cross_sell_opportunities(top_n=15)
            answer = _format_cross_sell(data, query)

        elif bi_type == "target_achievement":
            data = target_achievement()
            answer = _format_target_achievement(data, query)

        else:
            data = _extract_sales_filters(query)
            bi_data = sales_summary(**data)
            answer = _format_sales_summary(bi_data, query)
            data = bi_data

        elapsed = round(time.time() - start, 3)
        return ChatResponse(
            answer=answer,
            intent=BI_QUERY,
            confidence=0.95,
            sources=[],
            total_chunks_searched=0,
            response_time=elapsed,
            model_used="bi_engine",
            bi_data=data,
        )

    except Exception as e:
        logger.error(f"BI query failed: {e}")
        elapsed = round(time.time() - start, 3)
        return ChatResponse(
            answer=f"I encountered an error running that business intelligence query: {str(e)}",
            intent=BI_QUERY,
            confidence=0.0,
            sources=[],
            total_chunks_searched=0,
            response_time=elapsed,
            model_used="bi_engine",
        )


def _extract_sales_filters(query: str) -> dict:
    import re
    filters = {}

    sp_match = re.search(r"\b(sp\d+)\b", query.lower())
    if sp_match:
        filters["sales_person"] = sp_match.group(1).upper()

    year_match = re.search(r"\b(20\d\d)\b", query)
    if year_match:
        year = int(year_match.group(1))
        filters["fin_year"] = year if int(query[query.find(str(year))-1:query.find(str(year))].strip() or "7") >= 7 else year - 1

    return filters


# ── BI FORMATTERS ──────────────────────────────────────────────────────────

def _format_customer_growth(data: dict, query: str) -> str:
    results = data.get("results", [])
    summary = data.get("summary", {})
    stopped = data.get("stopped_buying", [])
    note    = data.get("note", "")

    if not results:
        return "No customer data available."

    lines = [
        f"**Customer Revenue & Growth Analysis** — Top {data['total']} customers\n",
        f"**Trend:** {summary.get('growing',0)} growing · {summary.get('stable',0)} stable · "
        f"{summary.get('declining',0)} declining · {summary.get('at_risk',0)} at risk · "
        f"{summary.get('h1_only',0)} H1 only · {summary.get('new_in_h2',0)} new in H2\n",
        f"_{note}_\n",
        "\n| Customer | Total Revenue | H1 (Jul–Dec) | H2 (Jan–Jun) | Trend |",
        "|----------|--------------|-------------|-------------|-------|",
    ]
    trend_emoji = {
        "Growing":   "📈",
        "Stable":    "➡️",
        "Declining": "📉",
        "At Risk":   "🚨",
        "H1 Only":   "⚠️",
        "New in H2": "🆕",
    }
    for r in results[:10]:
        emoji = trend_emoji.get(r["trend"], "")
        lines.append(
            f"| {r['customer_code']} "
            f"| £{r['total_rev']:,.0f} "
            f"| £{r['h1_rev']:,.0f} "
            f"| £{r['h2_rev']:,.0f} "
            f"| {emoji} {r['trend']} |"
        )

    if stopped:
        lines.append(f"\n**⚠️ Not yet active in FY2026:** {', '.join(stopped)}")

    return "\n".join(lines)


def _format_product_trends(data: dict, query: str) -> str:
    results = data.get("results", [])
    if not results:
        return "No product trend data available."

    hot     = [r for r in results if r["trend"] == "Hot"]
    growing = [r for r in results if r["trend"] == "Growing"]
    slowing = [r for r in results if r["trend"] == "Slowing"]
    decline = [r for r in results if r["trend"] == "Declining"]

    lines = [
        f"**Product Trends Analysis** — {data['total']} product types\n",
        f"🔥 **Hot ({len(hot)})** · 📈 **Growing ({len(growing)})** · 📉 **Slowing ({len(slowing)})** · ⬇️ **Declining ({len(decline)})**\n",
        "\n| Product Type | Revenue | YoY Growth | Trend |",
        "|-------------|---------|------------|-------|",
    ]
    for r in results[:12]:
        emoji = {"Hot": "🔥", "Growing": "📈", "Slowing": "📉", "Declining": "⬇️"}.get(r["trend"], "")
        lines.append(f"| {r['product_type']} | £{r['current_rev']:,.0f} | {r['yoy_growth_pct']:+.1f}% | {emoji} {r['trend']} |")

    return "\n".join(lines)


def _format_job_type_intelligence(data: dict, query: str) -> str:
    results = data.get("results", [])
    if not results:
        return "No job type data available."

    lines = [
        f"**Job Type Intelligence** — {data['total']} job types\n",
        "\n| Job Type | Revenue | Jobs | Avg Price | YoY Growth |",
        "|----------|---------|------|-----------|------------|",
    ]
    for r in results[:10]:
        growth = f"{r['yoy_growth_pct']:+.1f}%" if r["yoy_growth_pct"] else "N/A"
        lines.append(f"| {r['job_type']} | £{r['current_rev']:,.0f} | {r['current_jobs']} | £{r['avg_price']:,.0f} | {growth} |")

    return "\n".join(lines)


def _format_salesperson_analysis(data: dict, query: str) -> str:
    results = data.get("results", [])
    note    = data.get("note", "")
    if not results:
        return "No salesperson data available."

    lines = [
        f"**Salesperson Analysis** — {data['total']} salespeople\n",
        f"_{note}_\n",
        "\n| Salesperson | FY2025 (Full Year) | FY2026 YTD | Customers (YTD) | Rev/Customer | Status |",
        "|-------------|-------------------|------------|----------------|--------------|--------|",
    ]
    status_emoji = {"New": "🆕", "Gone": "👋", "Active": "✅"}
    for r in results:
        emoji  = status_emoji.get(r["status"], "")
        rev_pc = f"£{r['rev_per_customer']:,.0f}" if r.get("rev_per_customer") else "—"
        lines.append(
            f"| {r['sales_person']} "
            f"| £{r['full_rev']:,.0f} "
            f"| £{r['current_rev']:,.0f} "
            f"| {r['current_customers']} "
            f"| {rev_pc} "
            f"| {emoji} {r['status']} |"
        )

    active   = [r for r in results if r["status"] == "Active"]
    new_sps  = [r["sales_person"] for r in results if r["status"] == "New"]
    gone_sps = [r["sales_person"] for r in results if r["status"] == "Gone"]

    if active:
        top = max(active, key=lambda x: x["full_rev"])
        lines.append(f"\n**💡 Highest FY2025 revenue:** {top['sales_person']} — £{top['full_rev']:,.0f}")
    if new_sps:
        lines.append(f"**🆕 New this year:** {', '.join(new_sps)}")
    if gone_sps:
        lines.append(f"**👋 No FY2026 sales yet:** {', '.join(gone_sps)}")

    return "\n".join(lines)


def _format_cross_sell(data: dict, query: str) -> str:
    results = data.get("results", [])
    if not results:
        return "No cross-sell opportunities found."

    lines = [
        f"**Cross-Sell Opportunities** — {data['total']} high-potential customers\n",
        f"_{data.get('insight', '')}_\n",
        "\n| Customer | Revenue | Jobs | Work Stream | Products Used |",
        "|----------|---------|------|-------------|---------------|",
    ]
    for r in results[:10]:
        lines.append(
            f"| {r['customer_code']} | £{r['total_revenue']:,.0f} | "
            f"{r['total_jobs']} | {r['work_streams_list']} | {r['products_used']} |"
        )

    return "\n".join(lines)


def _format_target_achievement(data: dict, query: str) -> str:
    results = data.get("results", [])
    if not results:
        return "No target achievement data available."

    met   = data.get("met_target", 0)
    total = data.get("total", 0)
    avg   = data.get("avg_target", 0)

    lines = [
        f"**Target Achievement** — Current Financial Year\n",
        f"**{met} of {total} salespeople** met their target · Average target: £{avg:,.0f}\n",
        "\n| Salesperson | Revenue | Achievement | Target Met |",
        "|-------------|---------|-------------|------------|",
    ]
    for r in results:
        emoji = "✅" if r["met_target"] else "❌"
        lines.append(
            f"| {r['sales_person']} | £{r['revenue']:,.0f} | "
            f"{r['achievement']}% | {emoji} |"
        )

    return "\n".join(lines)


def _format_sales_summary(data: dict, query: str) -> str:
    s = data.get("summary", {})
    if not s or not s.get("total_jobs"):
        return "No sales data found for those filters."

    filters = data.get("filters", {})
    filter_desc = " · ".join(
        f"{k}: {v}" for k, v in filters.items() if v
    ) or "All records"

    lines = [
        f"**Sales Summary** — {filter_desc}\n",
        f"- **Total Revenue:** £{s.get('total_revenue', 0):,.2f}",
        f"- **Total Jobs:** {s.get('total_jobs', 0)}",
        f"- **Avg Job Value:** £{s.get('avg_job_value', 0):,.2f}",
        f"- **Unique Customers:** {s.get('unique_customers', 0)}",
        f"- **Unique Products:** {s.get('unique_products', 0)}",
        f"- **Date Range:** {s.get('first_sale', '')} to {s.get('last_sale', '')}",
    ]

    top_customers = data.get("top_customers", [])
    if top_customers:
        lines.append("\n**Top Customers:**")
        lines.append("\n| Customer | Revenue | Jobs |")
        lines.append("|----------|---------|------|")
        for c in top_customers:
            lines.append(f"| {c['customer_code']} | £{c['revenue']:,.2f} | {c['jobs']} |")

    return "\n".join(lines)


# ── ESTIMATION HANDLER ─────────────────────────────────────────────────────

def handle_estimation(query: str, session_id: str) -> ChatResponse:
    start = time.time()
    result = handle_estimation_message(query, session_id=session_id)
    elapsed = round(time.time() - start, 3)

    return ChatResponse(
        answer=result["answer"],
        intent=ESTIMATION,
        confidence=1.0,
        sources=[],
        total_chunks_searched=0,
        response_time=elapsed,
        model_used=settings.GROQ_MODEL,
        jobs=result.get("jobs", []),
        jobs_table=result.get("jobs_table", ""),
        is_estimation=True,
        prediction=result.get("prediction"),
    )


# ── MAIN CHAT FUNCTION ─────────────────────────────────────────────────────

def chat(
    query: str,
    session_id: str = "default",
    top_k: int = settings.DEFAULT_TOP_K,
    min_technicality: float = settings.DEFAULT_MIN_TECHNICALITY,
) -> ChatResponse:
    start = time.time()
    logger.info(f"Query: '{query[:60]}' | session: {session_id}")

    # ── STEP 1: CHECK ACTIVE SESSIONS FIRST ───────────────────────────────

    if is_knn_session_active(session_id):
        logger.info("→ KNN session active — routing to KNN bridge")
        try:
            knn_result = handle_knn_message(
                user_message=query,
                session_id=session_id,
                product_type_id="LA",
            )
            elapsed = round(time.time() - start, 3)
            return ChatResponse(
                answer=knn_result["answer"],
                intent="knn_estimation",
                confidence=1.0,
                sources=[],
                total_chunks_searched=0,
                response_time=elapsed,
                model_used="knn_gower",
                is_estimation=True,
                prediction={
                    "result": knn_result.get("result"),
                    "form_fields": knn_result.get("form_fields"),
                    "questions_remaining": knn_result.get("questions_remaining"),
                    "completed": knn_result.get("completed"),
                },
            )
        except Exception as e:
            logger.warning(f"KNN chatbot_bridge failed: {e} — falling through")
            clear_knn_session(session_id)

    from chatbot.estimation_flow import _sessions
    legacy_session = _sessions.get(session_id)
    legacy_active  = legacy_session is not None and not legacy_session.jobs_shown

    if legacy_active:
        logger.info("→ Legacy estimation session active — routing to estimation_flow")
        return handle_estimation(query, session_id)

    # ── FIX B3: Auto-reset completed session on ANY new estimation intent ──
    # Previously this only reset when is_estimation_query() matched,
    # which missed some phrasings. Now we reset on ESTIMATION intent
    # from the classifier — much more reliable.
    if legacy_session and legacy_session.jobs_shown:
        intent_check = classify_intent(query)
        if intent_check.intent == ESTIMATION:
            from chatbot.estimation_flow import clear_session
            clear_session(session_id)
            logger.info("Cleared completed estimation session — starting fresh (intent=ESTIMATION)")

    # ── STEP 2: CLASSIFY INTENT ────────────────────────────────────────────

    intent_result = classify_intent(query)
    logger.info(
        f"Intent: {intent_result.intent} "
        f"({intent_result.confidence:.2f}) — {intent_result.reason}"
    )

    # ── STEP 3: ROUTE NEW MESSAGES ─────────────────────────────────────────

    if intent_result.intent == ESTIMATION:
        roofing_keywords = [
            "liquid applied", "liquid-applied", "roofing", "waterproof",
            "roof membrane", "flat roof", "weathertight", "wind uplift",
        ]
        is_roofing_query = any(kw in query.lower() for kw in roofing_keywords)

        if is_roofing_query:
            logger.info("→ New roofing estimation — routing to KNN bridge")
            try:
                knn_result = handle_knn_message(
                    user_message=query,
                    session_id=session_id,
                    product_type_id="LA",
                )
                elapsed = round(time.time() - start, 3)
                return ChatResponse(
                    answer=knn_result["answer"],
                    intent="knn_estimation",
                    confidence=1.0,
                    sources=[],
                    total_chunks_searched=0,
                    response_time=elapsed,
                    model_used="knn_gower",
                    is_estimation=True,
                    prediction={
                        "result": knn_result.get("result"),
                        "form_fields": knn_result.get("form_fields"),
                        "questions_remaining": knn_result.get("questions_remaining"),
                        "completed": knn_result.get("completed"),
                    },
                )
            except Exception as e:
                logger.warning(f"KNN failed on initial query: {e} — falling to legacy")

        logger.info("→ New estimation — routing to legacy estimation_flow")
        return handle_estimation(query, session_id)

    if intent_result.intent == BI_QUERY:
        logger.info(f"→ Routing to BI engine: {intent_result.bi_type}")
        return handle_bi_query(query, intent_result.bi_type)

    if intent_result.intent in [TECHNICAL, UNKNOWN]:
        logger.info("→ Routing to technical retrieval")
        retrieval_result = search(
            query=query,
            top_k=top_k,
            min_technicality=min_technicality,
        )
        chunks    = retrieval_result["results"]
        total_raw = retrieval_result["total_raw"]

        system_prompt, user_message = build_prompt(
            query=query,
            intent=intent_result.intent,
            chunks=chunks,
        )

        answer = call_llm(
            system_prompt=system_prompt,
            user_message=user_message,
        )

        elapsed = round(time.time() - start, 3)
        sources = [
            {
                "source":      chunk.get("source", ""),
                "doc_id":      chunk.get("doc_id", ""),
                "confidence":  chunk.get("confidence", ""),
                "fused_score": chunk.get("fused_score", 0),
                "standards":   chunk.get("standards", [])[:2],
            }
            for chunk in chunks
        ]

        return ChatResponse(
            answer=answer,
            intent=intent_result.intent,
            confidence=intent_result.confidence,
            sources=sources,
            total_chunks_searched=total_raw,
            response_time=elapsed,
            model_used=settings.GROQ_MODEL,
        )

    # ── GREETING ───────────────────────────────────────────────────────────

    system_prompt, user_message = build_prompt(
        query=query,
        intent=GREETING,
        chunks=[],
    )
    answer  = call_llm(system_prompt=system_prompt, user_message=user_message)
    elapsed = round(time.time() - start, 3)

    return ChatResponse(
        answer=answer,
        intent=GREETING,
        confidence=1.0,
        sources=[],
        total_chunks_searched=0,
        response_time=elapsed,
        model_used=settings.GROQ_MODEL,
    )