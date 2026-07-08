import json
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from app.logger import get_logger

logger = get_logger("estimation_flow")

QUESTION_ORDER = ["product_type", "job_type", "est_hrs", "dimensions", "temperature"]
REQUIRED_FIELDS = ["product_type", "job_type", "est_hrs", "dimensions", "temperature"]

FIELD_QUESTIONS = {
    "product_type": "What type of product or material needs to be tested or certified?\n(e.g. cladding, render, roof insulation, screed, plasterboard)",
    "job_type":     "What type of job is this?\n(e.g. Additional Product Sheet, Amendment, Assessment, Standard, Technical Reissue)",
    "est_hrs":      "Do you have an initial hours estimate for this job? If not, just say **no** and I will calculate one from historical data.",
    "dimensions":   "What are the dimensions of the test specimen?\n(e.g. 10x4 metres, 16mm thick, or just 10x5) — or say **skip** to continue without this.",
    "temperature":  "Is there a specific temperature requirement?\n(e.g. 240°C) — or say **none** if not applicable.",
}

NEVER_INFER      = ["job_type", "dimensions", "temperature"]
SKIP_EXACT       = {"skip", "n/a", "not sure", "don't know", "unsure", "na", "none"}
EST_HRS_SKIP_EXACT = {"no", "nope", "skip", "n/a", "not sure", "don't know", "unsure", "na", "none"}

KNOWN_JOB_TYPES = [
    "Non Technical Reissue",
    "Additional Product Sheet",
    "Technical Reissue",
    "Contract Variation",
    "Factory Production Control",
    "Amendment",
    "Assessment",
    "Reproduction",
    "Standard",
    "Audit",
]

BAD_PHRASES = [
    "any dimensions mentioned", "any temperature mentioned",
    "null", "not mentioned", "any dimensions", "any temperature",
    "not specified", "unknown",
]

HOURLY_RATE_GBP = 95.0

PRODUCT_KEYWORD_MAP = {
    "render":           "RE - Render",
    "rendering":        "RE - Render",
    "plaster":          "RE - Render",
    "cladding":         "CL - Cladding",
    "facade":           "CL - Cladding",
    "plasterboard":     "PP - Passive Fire Protection Sheet",
    "fire board":       "PP - Passive Fire Protection Sheet",
    "passive fire":     "PP - Passive Fire Protection Sheet",
    "board":            "PP - Passive Fire Protection Sheet",
    "roof insulation":  "RI - Roof Insulation",
    "roofing":          "RI - Roof Insulation",
    "roof":             "RI - Roof Insulation",
    "screed":           "SC - Screed",
    "floor screed":     "SC - Screed",
    "tanking":          "TA - Tanking",
    "waterproof":       "TA - Tanking",
    "insulation":       "EW - External Wall Insulation",
    "wall insulation":  "EW - External Wall Insulation",
    "block":            "TB - Building Block",
    "building block":   "TB - Building Block",
    "mortar":           "MO - Mortar",
    "lintel":           "LI - Lintel",
    "window":           "WI - Window System Supplier",
    "door":             "AF - Window and Door Hardware",
    "drainage":         "ID - Internal Drainage Membrane (wall)",
    "damp":             "DN - Damp-proof Course (new)",
    "slate":            "SL - Roofing Slate",
    "membrane":         "LA - Roofing (liquid-applied)",
    "liquid applied":   "LA - Roofing (liquid-applied)",
}

GROQ_EXTRACTABLE = {"product_type", "est_hrs"}

EXTRACT_SYSTEM_PROMPT = """You are extracting structured information from a construction job description.

Return ONLY a valid JSON object. Only include fields explicitly stated by the user.

Fields to extract:
{
  "product_type": "match to known code e.g. CL - Cladding, RE - Render, TB - Building Block",
  "est_hrs": number (only if user gives a specific number of hours)
}

Common product type mappings:
- plasterboard, board, gypsum board = TB - Building Block
- fire board, passive fire = PP - Passive Fire Protection Sheet
- render, rendering, plaster = RE - Render
- cladding, facade = CL - Cladding
- roof insulation, roofing = RI - Roof Insulation
- screed, floor screed = SC - Screed
- tanking, waterproof = TA - Tanking
- insulation, wall insulation = EW - External Wall Insulation

IMPORTANT RULES:
1. NEVER extract job_type, dimensions, or temperature — these are always asked separately
2. Only extract est_hrs if the user gives an explicit number like "40 hours" or "we estimate 60 hrs"
3. If a field is not clearly stated, omit it entirely

Return ONLY the JSON object. No explanation. No markdown."""


@dataclass
class EstimationSession:
    collected:       Dict[str, Any]       = field(default_factory=dict)
    history:         List[Dict[str, str]] = field(default_factory=list)
    questions_asked: List[str]            = field(default_factory=list)
    jobs_shown:      bool                 = False
    prediction_done: bool                 = False
    topic:           str                  = ""


_sessions: Dict[str, EstimationSession] = {}


def get_or_create_session(session_id: str) -> EstimationSession:
    if session_id not in _sessions:
        _sessions[session_id] = EstimationSession()
    return _sessions[session_id]


def clear_session(session_id: str):
    if session_id in _sessions:
        del _sessions[session_id]


def is_bad_value(value: Any) -> bool:
    if not value:
        return True
    if isinstance(value, str):
        return value.lower().strip() in BAD_PHRASES
    return False


def keyword_match_product_type(text: str) -> Optional[str]:
    text_lower = text.lower().strip()
    for keyword in sorted(PRODUCT_KEYWORD_MAP.keys(), key=len, reverse=True):
        if keyword in text_lower:
            return PRODUCT_KEYWORD_MAP[keyword]
    return None


def _match_job_type(msg_lower: str) -> Optional[str]:
    for jt in KNOWN_JOB_TYPES:
        if msg_lower == jt.lower():
            return jt

    msg_words = set(msg_lower.split())
    best_match = None
    best_score = 0
    for jt in KNOWN_JOB_TYPES:
        jt_words = set(jt.lower().split())
        overlap  = msg_words & jt_words
        if overlap == msg_words and len(overlap) / len(jt_words) >= 0.5:
            score = len(overlap)
            if score > best_score:
                best_score = score
                best_match = jt

    return best_match


def extract_fields(text: str) -> Dict[str, Any]:
    from chatbot.llm_client import call_llm
    try:
        response = call_llm(
            system_prompt=EXTRACT_SYSTEM_PROMPT,
            user_message=text,
            max_tokens=200,
            temperature=0.0,
        )
        response = re.sub(r"```(?:json)?", "", response).strip()
        start = response.find("{")
        end   = response.rfind("}") + 1
        if start == -1 or end == 0:
            return {}
        extracted = json.loads(response[start:end])

        clean = {}
        for k in GROQ_EXTRACTABLE:
            v = extracted.get(k)
            if v and v != "null" and not is_bad_value(str(v)):
                clean[k] = v
        return clean

    except Exception as e:
        logger.warning(f"Field extraction failed: {e}")
        return {}


def detect_topic_change(new_message: str, current_topic: str) -> bool:
    if not current_topic:
        return False

    new_project_signals = [
        "we got a project", "we have a project", "new project",
        "we need to estimate", "quote for", "estimate for",
        "another project", "different project",
    ]

    msg_lower = new_message.lower()
    for signal in new_project_signals:
        if signal in msg_lower:
            product_keywords = [
                "cladding", "render", "plasterboard", "screed",
                "insulation", "roofing", "roof", "tanking", "block"
            ]
            for kw in product_keywords:
                if kw in msg_lower and kw not in current_topic.lower():
                    return True
    return False


def resolve_est_hrs(prod_type: str, job_type: str) -> float:
    try:
        from predictor.predict import load_model
        _, meta = load_model()
        prod_stat = meta["prod_stats"].get(prod_type, {})
        job_stat  = meta["job_stats"].get(job_type, {})
        avg = prod_stat.get("avg_est_hrs") or job_stat.get("avg_act_hrs") or 40.0
        logger.info(f"Using historical avg est_hrs: {avg} for {prod_type}")
        return round(float(avg), 1)
    except Exception:
        return 40.0


def run_prediction(collected: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from predictor.predict import predict_effort
        return predict_effort(
            prod_type=collected.get("product_type", "CL - Cladding"),
            job_type=collected.get("job_type", "Additional Product Sheet"),
            est_hrs=float(collected.get("est_hrs", 40.0)),
        )
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        return {}


def get_similar_jobs(collected: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        from predictor.predict import find_similar_jobs
        return find_similar_jobs(
            prod_type=collected.get("product_type", ""),
            job_type=collected.get("job_type", ""),
            max_results=8,
        )
    except Exception as e:
        logger.error(f"Similar jobs failed: {e}")
        return []


def format_prediction_block(prediction: Dict[str, Any]) -> str:
    if not prediction:
        return ""

    risk_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(prediction.get("risk_flag", "MEDIUM"), "🟡")
    conf_emoji = {"HIGH": "✅", "MEDIUM": "⚠️", "LOW": "❓"}.get(prediction.get("confidence", "MEDIUM"), "⚠️")

    prod_stat    = prediction.get("prod_stats", {})
    overrun_rate = round(prod_stat.get("overrun_rate", 0.5) * 100)

    pred_hrs  = prediction.get("predicted_hrs", 0)
    low_hrs   = prediction.get("low_hrs", 0)
    high_hrs  = prediction.get("high_hrs", 0)

    cost_mid  = round(pred_hrs  * HOURLY_RATE_GBP, 2)
    cost_low  = round(low_hrs   * HOURLY_RATE_GBP, 2)
    cost_high = round(high_hrs  * HOURLY_RATE_GBP, 2)

    lines = [
        "## 📊 Effort & Cost Prediction\n",
        "| | Hours | Estimated Cost |",
        "|---|---|---|",
        f"| **Predicted** | **{pred_hrs} hrs** | **£{cost_mid:,.2f}** |",
        f"| **80% Range** | {low_hrs} – {high_hrs} hrs | £{cost_low:,.2f} – £{cost_high:,.2f} |",
        "",
        "| | |",
        "|---|---|",
        f"| **Model Confidence** | {conf_emoji} {prediction.get('confidence', 'N/A')} |",
        f"| **Overrun Risk** | {risk_emoji} {prediction.get('risk_flag', 'N/A')} |",
        f"| **Historical Overrun Rate** | {overrun_rate}% of similar jobs exceed estimate |",
        f"\n_{prediction.get('risk_reason', '')}_",
        f"\n> Model trained on historical jobs · Accuracy: ±{prediction.get('cv_mae', 'N/A')} hrs · Rate: £{HOURLY_RATE_GBP}/hr",
    ]
    return "\n".join(lines)


def format_jobs_table(jobs: List[Dict[str, Any]]) -> str:
    if not jobs:
        return "_No similar historical jobs found in the database._"

    lines = [
        "## 📋 Similar Historical Jobs\n",
        "| Job No | Product Type | Job Type | Est Hrs | Act Hrs | Variation | Budget |",
        "|--------|-------------|----------|---------|---------|-----------|--------|",
    ]
    for j in jobs:
        var = j.get("variation") or 0
        budget_emoji = "🔴" if var > 0 else "🟢" if var < 0 else "🟡"
        budget_label = "Over" if var > 0 else "Under" if var < 0 else "On budget"
        lines.append(
            f"| {j['job_no']} "
            f"| {j['prod_type']} "
            f"| {j['job_type']} "
            f"| {j['est_hrs']} "
            f"| {j['act_hrs']} "
            f"| {j['variation_label']} "
            f"| {budget_emoji} {budget_label} |"
        )
    return "\n".join(lines)


def is_estimation_query(query: str) -> bool:
    keywords = [
        "quote", "estimate", "quotation", "estimation",
        "similar jobs", "how long", "how many hours",
        "effort", "scope", "we got a", "we have a", "new project",
        "testing", "certification project", "predict hours",
        "job hours", "time to complete", "we need to estimate",
    ]
    q = query.lower()
    return any(kw in q for kw in keywords)


def _capture_dimensions(user_message: str) -> Optional[str]:
    msg = user_message.strip()

    m = re.search(
        r"(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)"
        r"\s*(?:m|metres?|meters?)",
        msg, re.IGNORECASE
    )
    if m:
        return f"{m.group(1)} x {m.group(2)} x {m.group(3)} metres"

    m = re.search(
        r"(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)",
        msg, re.IGNORECASE
    )
    if m:
        return f"{m.group(1)} x {m.group(2)} x {m.group(3)}"

    m = re.search(
        r"(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:m|metres?|meters?)",
        msg, re.IGNORECASE
    )
    if m:
        return f"{m.group(1)} x {m.group(2)} metres"

    m = re.search(
        r"(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)",
        msg, re.IGNORECASE
    )
    if m:
        return f"{m.group(1)} x {m.group(2)} metres"

    m = re.search(r"(\d+(?:\.\d+)?)\s*mm\b", msg, re.IGNORECASE)
    if m:
        return f"{m.group(1)}mm"

    return None


def _capture_temperature(user_message: str) -> Optional[str]:
    patterns = [
        r"(\d+(?:\.\d+)?)\s*(?:°\s*c|degrees?\s*c|celsius)",
        r"(\d+(?:\.\d+)?)\s*°",
        r"(\d+(?:\.\d+)?)\s*degrees?",
        r"^(\d+(?:\.\d+)?)$",
    ]
    for pat in patterns:
        m = re.search(pat, user_message.strip(), re.IGNORECASE)
        if m:
            return f"{m.group(1)}°C"
    return None


def handle_estimation_message(
    user_message: str,
    session_id: str = "default",
) -> Dict[str, Any]:
    session = get_or_create_session(session_id)

    if session.jobs_shown:
        new_project_signals = [
            "we got a project", "we have a project", "new project",
            "we need to estimate", "quote for", "estimate for",
            "another project", "different project", "testing project",
            "certification project", "need to quote",
        ]
        if any(sig in user_message.lower() for sig in new_project_signals):
            logger.info(f"New estimation after completed session — resetting {session_id}")
            _sessions[session_id] = EstimationSession()
            session = _sessions[session_id]

    if detect_topic_change(user_message, session.topic):
        logger.info(f"Topic change detected — resetting session {session_id}")
        _sessions[session_id] = EstimationSession()
        session = _sessions[session_id]

    session.history.append({"role": "user", "content": user_message})

    extracted = extract_fields(user_message)
    logger.info(f"Extracted by Groq: {extracted}")

    if "product_type" not in extracted and "product_type" not in session.collected:
        kw_match = keyword_match_product_type(user_message)
        if kw_match:
            extracted["product_type"] = kw_match
            logger.info(f"Keyword fallback matched product_type: {kw_match}")

    if "product_type" in extracted and not session.topic:
        session.topic = extracted["product_type"]

    # Guard: once product_type is locked in for this session, Groq must not
    # silently overwrite it on later turns (e.g. it was hallucinating off
    # the word "Amendment" and returned "TB - Building Block").
    if "product_type" in extracted and "product_type" in session.collected:
        del extracted["product_type"]

    # Guard: only trust Groq's est_hrs if the question has actually been
    # asked AND the user's message contains a real number. Otherwise Groq
    # is hallucinating a value (e.g. defaulting to 40 on "Amendment").
    if "est_hrs" in extracted:
        est_hrs_asked = "est_hrs" in session.questions_asked
        has_digit     = bool(re.search(r"\d+(?:\.\d+)?", user_message))
        if not est_hrs_asked or not has_digit:
            logger.warning(
                f"Discarding hallucinated est_hrs={extracted['est_hrs']} "
                f"from Groq (asked={est_hrs_asked}, digits_in_msg={has_digit}, msg='{user_message}')"
            )
            del extracted["est_hrs"]

    for k in GROQ_EXTRACTABLE:
        if k in extracted:
            session.collected[k] = extracted[k]

    msg_lower = user_message.lower().strip()
    msg_exact = user_message.strip()

    if "est_hrs" not in session.collected and "est_hrs" in session.questions_asked:
        if msg_lower in EST_HRS_SKIP_EXACT:
            session.collected["est_hrs"] = resolve_est_hrs(
                session.collected.get("product_type", ""),
                session.collected.get("job_type", ""),
            )
            logger.info(f"est_hrs auto-resolved: {session.collected['est_hrs']}")
        else:
            nums = re.findall(r"\d+(?:\.\d+)?", msg_exact)
            if nums:
                session.collected["est_hrs"] = float(nums[0])
                logger.info(f"est_hrs from user: {nums[0]}")

    if "job_type" not in session.collected and "job_type" in session.questions_asked:
        matched_jt = _match_job_type(msg_lower)
        if matched_jt:
            session.collected["job_type"] = matched_jt
            logger.info(f"Job type captured: {matched_jt}")
        elif len(msg_exact) < 50:
            session.collected["job_type"] = msg_exact.title()
            logger.info(f"Job type raw fallback: {msg_exact.title()}")

    if "dimensions" in session.questions_asked and "dimensions" not in session.collected:
        if msg_lower in SKIP_EXACT:
            session.collected["dimensions"] = None
            logger.info("Dimensions skipped by user")
        else:
            captured_dim = _capture_dimensions(user_message)
            if captured_dim:
                session.collected["dimensions"] = captured_dim
                logger.info(f"Dimensions captured: {captured_dim}")
            else:
                session.collected["dimensions"] = None
                logger.info("Dimensions not parseable — treating as skipped")

    if "temperature" in session.questions_asked and "temperature" not in session.collected:
        if msg_lower in SKIP_EXACT or msg_lower == "none":
            session.collected["temperature"] = None
            logger.info("Temperature skipped")
        else:
            captured_temp = _capture_temperature(user_message)
            if captured_temp:
                session.collected["temperature"] = captured_temp
                logger.info(f"Temperature captured: {captured_temp}")
            else:
                session.collected["temperature"] = None
                logger.info("Temperature not parseable — treating as skipped")

    REQUIRED = {"product_type", "job_type", "est_hrs"}

    next_question = None
    for f in QUESTION_ORDER:
        already_collected = f in session.collected
        already_asked     = f in session.questions_asked

        if already_collected:
            continue

        if f in REQUIRED:
            next_question = f
            break
        else:
            if already_asked:
                continue
            next_question = f
            break

    core_collected = all(f in session.collected for f in ["product_type", "job_type", "est_hrs"])
    optional_done  = (
        ("dimensions"  in session.questions_asked or "dimensions"  in session.collected) and
        ("temperature" in session.questions_asked or "temperature" in session.collected)
    )
    all_done = core_collected and optional_done

    if next_question and not session.jobs_shown:
        question = FIELD_QUESTIONS[next_question]
        if next_question not in session.questions_asked:
            session.questions_asked.append(next_question)

        ack = ""
        if extracted:
            got = ", ".join(
                f"**{k.replace('_', ' ').title()}**: {v}"
                for k, v in extracted.items()
                if k in ["product_type", "est_hrs"] and v
            )
            if got:
                ack = f"Got it — {got}.\n\n"

        answer = f"{ack}{question}"
        session.history.append({"role": "assistant", "content": answer})

        return {
            "answer":     answer,
            "jobs":       [],
            "jobs_table": "",
            "prediction": None,
            "collected":  session.collected,
            "missing":    [next_question],
            "ready":      False,
        }

    if not all_done:
        for f in ["product_type", "job_type", "est_hrs"]:
            if f not in session.collected:
                question = FIELD_QUESTIONS[f]
                if f not in session.questions_asked:
                    session.questions_asked.append(f)
                session.history.append({"role": "assistant", "content": question})
                return {
                    "answer": question,
                    "jobs": [], "jobs_table": "",
                    "prediction": None,
                    "collected": session.collected,
                    "missing": [f],
                    "ready": False,
                }

    logger.info(f"All fields collected — running prediction: {session.collected}")

    prediction = run_prediction(session.collected)
    jobs       = get_similar_jobs(session.collected)

    session.jobs_shown      = True
    session.prediction_done = True

    pred_block = format_prediction_block(prediction)
    jobs_block = format_jobs_table(jobs)

    summary_lines = [
        "## ✅ Estimation Complete\n",
        "**Job Details Collected:**",
        f"- **Product Type** : {session.collected.get('product_type', 'N/A')}",
        f"- **Job Type**     : {session.collected.get('job_type', 'N/A')}",
        f"- **Est. Hours**   : {session.collected.get('est_hrs', 'N/A')} hrs",
    ]

    dim  = session.collected.get("dimensions")
    temp = session.collected.get("temperature")

    if dim and not is_bad_value(str(dim)):
        summary_lines.append(f"- **Dimensions**   : {dim}")
    if temp and not is_bad_value(str(temp)):
        summary_lines.append(f"- **Temperature**  : {temp}")

    answer = (
        "\n".join(summary_lines) + "\n\n" +
        pred_block + "\n\n" +
        jobs_block + "\n\n" +
        "_Would you like to refine the estimate, ask about a specific job, or start a new estimation?_"
    )

    session.history.append({"role": "assistant", "content": answer})

    return {
        "answer":     answer,
        "jobs":       jobs,
        "jobs_table": jobs_block,
        "prediction": prediction,
        "collected":  session.collected,
        "missing":    [],
        "ready":      True,
        "summary": {
            "predicted_hrs": prediction.get("predicted_hrs"),
            "risk_flag":     prediction.get("risk_flag"),
            "confidence":    prediction.get("confidence"),
            "similar_jobs":  len(jobs),
        }
    }