"""
Chatbot Bridge — connects the KNN pipeline to the CertIQ chatbot.

FIX LOG:
- Bug 1: session_id must be stable across turns — callers must pass a
         consistent conversation session_id, not a per-message UUID.
- Bug 2: questions_asked append moved to single location only.
- Bug 3: "no" removed from skip_words for boolean questions.
- Bug 4: conf_emoji uses .get() with fallback — no KeyError.
- Bug 5: questions_remaining only removed after valid answer stored.
- Bug 6: Added COST ESTIMATION to the final result output.
         Uses same £95/hr rate as estimation_flow for consistency.
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from app.logger import get_logger

logger = get_logger("chatbot_bridge")

HOURLY_RATE_GBP = 95.0  # BBA certification average — keep in sync with estimation_flow.py

# ── SESSION STATE ──────────────────────────────────────────────────────────
@dataclass
class KNNSession:
    product_type_id:     str            = "LA"
    answers:             Dict[str, Any] = field(default_factory=dict)
    questions_asked:     List[str]      = field(default_factory=list)
    questions_remaining: List[Dict]     = field(default_factory=list)
    result:              Optional[Dict] = None
    completed:           bool           = False
    source:              str            = "chatbot"


_knn_sessions: Dict[str, KNNSession] = {}


def get_or_create_knn_session(session_id: str) -> KNNSession:
    if session_id not in _knn_sessions:
        _knn_sessions[session_id] = KNNSession()
    return _knn_sessions[session_id]


def clear_knn_session(session_id: str):
    if session_id in _knn_sessions:
        del _knn_sessions[session_id]


def is_knn_session_active(session_id: str) -> bool:
    s = _knn_sessions.get(session_id)
    return s is not None and not s.completed


def handle_knn_message(
    user_message: str,
    session_id: str = "default",
    product_type_id: str = "LA",
) -> Dict[str, Any]:
    """
    Main handler for KNN estimation in chatbot.
    session_id MUST be stable across the whole conversation.
    """
    if not session_id or session_id == "default":
        logger.warning(
            "handle_knn_message called with generic session_id='%s'. "
            "Each conversation needs a stable unique session_id.",
            session_id,
        )

    session = get_or_create_knn_session(session_id)
    session.product_type_id = product_type_id

    # MODE 0: Form submission resubmitting all values at once
    if user_message.strip().startswith("form_submit:"):
        try:
            answers_json = user_message.strip()[len("form_submit:"):].strip()
            submitted_answers = json.loads(answers_json)
            from certiq.forms import run_inference_from_form
            result = run_inference_from_form(
                form_data=submitted_answers,
                product_type_id=session.product_type_id,
                k=3,
                session_id=session_id,
            )
            session.completed = True
            session.result = result
            return {
                "answer":    format_final_result(result),
                "result":    result,
                "completed": True,
            }
        except Exception as e:
            logger.error("Failed to parse/run form submit: %s", e)

    # MODE 1: First message
    if not session.questions_asked and not session.questions_remaining:
        return _handle_first_message(user_message, session, session_id)

    # MODE 2: Collecting answers
    if session.questions_remaining:
        return _handle_form_answer(user_message, session, session_id)

    # MODE 3: Already done
    if session.completed and session.result:
        return {
            "answer":    format_final_result(session.result),
            "result":    session.result,
            "completed": True,
        }

    return _run_knn_and_return(session, session_id)


def _handle_first_message(
    text: str,
    session: KNNSession,
    session_id: str,
) -> Dict[str, Any]:
    from certiq.parser import parse_any
    from certiq.extractor import extract_attributes
    from certiq.forms import get_dynamic_form

    doc          = parse_any(text)
    attr_results = extract_attributes(doc, session.product_type_id, use_llm=False)

    for attr_name, result in attr_results.items():
        if result["is_present"]:
            session.answers[attr_name] = {
                "value":      result.get("value", "Yes"),
                "confidence": result.get("confidence", 0.5),
                "source":     "extracted",
            }

    form       = get_dynamic_form(session.product_type_id)
    all_fields = form["all_fields"]

    unanswered = [f for f in all_fields if f["attr_name"] not in session.answers]
    required   = [f for f in unanswered if f["is_required"]]
    optional   = [f for f in unanswered if not f["is_required"]]
    session.questions_remaining = required + optional

    found_attrs = [k.replace("_", " ").title() for k in session.answers]
    ack = f"I found these details in your description: **{', '.join(found_attrs)}**.\n\n" if found_attrs else ""

    required_names   = {f["attr_name"] for f in form["required_fields"]}
    missing_required = required_names - set(session.answers.keys())

    if not missing_required and not optional:
        return _run_knn_and_return(session, session_id)

    if session.questions_remaining:
        next_q = session.questions_remaining[0]
        session.questions_asked.append(next_q["attr_name"])  # append HERE only

        total    = len(all_fields)
        answered = len(session.answers)
        progress = f"({answered + 1}/{total})"

        answer = (
            f"{ack}To give you an accurate estimate, I need a few more details. {progress}\n\n"
            f"**{next_q['display_name']}**\n{next_q['question']}"
        )
        if next_q.get("hint"):
            answer += f"\n_{next_q['hint']}_"

        return {
            "answer":              answer,
            "collected_so_far":    session.answers,
            "questions_remaining": len(session.questions_remaining),
            "completed":           False,
            "form_fields":         all_fields,
        }

    return _run_knn_and_return(session, session_id)


def _handle_form_answer(
    user_message: str,
    session: KNNSession,
    session_id: str,
) -> Dict[str, Any]:
    from certiq.forms import get_dynamic_form

    last_asked    = session.questions_asked[-1] if session.questions_asked else None
    answer_stored = False

    if last_asked and session.questions_remaining:
        form   = get_dynamic_form(session.product_type_id)
        fields = {f["attr_name"]: f for f in form["all_fields"]}
        fld    = fields.get(last_asked, {})

        msg_lower  = user_message.lower().strip()
        skip_words = {"skip", "n/a", "not applicable", "not sure", "unknown"}

        if fld.get("field_type") == "boolean":
            yes_words = {"yes", "y", "true", "1", "required", "needed", "x"}
            is_yes    = any(w in msg_lower for w in yes_words)
            session.answers[last_asked] = {
                "value":      "Yes" if is_yes else "No",
                "confidence": 1.0,
                "source":     "form",
            }
            answer_stored = True

        elif fld.get("field_type") == "number":
            import re as _re
            nums = _re.findall(r"\d+(?:\.\d+)?", user_message)
            if nums and msg_lower not in skip_words:
                unit = fld.get("unit", "")
                session.answers[last_asked] = {
                    "value":      f"{nums[0]} {unit}".strip(),
                    "confidence": 1.0,
                    "source":     "form",
                }
                answer_stored = True
            elif msg_lower in skip_words:
                session.answers[last_asked] = {"value": None, "confidence": 1.0, "source": "form_skipped"}
                answer_stored = True

        else:
            if msg_lower in skip_words:
                session.answers[last_asked] = {"value": None, "confidence": 1.0, "source": "form_skipped"}
                answer_stored = True
            elif user_message.strip():
                session.answers[last_asked] = {
                    "value":      user_message.strip(),
                    "confidence": 1.0,
                    "source":     "form",
                }
                answer_stored = True

        if answer_stored:
            session.questions_remaining = [
                q for q in session.questions_remaining if q["attr_name"] != last_asked
            ]
        else:
            fld_def = fields.get(last_asked, {})
            re_ask  = (
                f"I didn't quite catch that. "
                f"**{fld_def.get('display_name', last_asked)}**\n"
                f"{fld_def.get('question', '')}"
            )
            if fld_def.get("hint"):
                re_ask += f"\n_{fld_def['hint']}_"
            return {
                "answer":              re_ask,
                "collected_so_far":    session.answers,
                "questions_remaining": len(session.questions_remaining),
                "completed":           False,
            }

    if session.questions_remaining:
        next_q = session.questions_remaining[0]
        session.questions_asked.append(next_q["attr_name"])  # append HERE only

        form     = get_dynamic_form(session.product_type_id)
        total    = len(form["all_fields"])
        answered = len(session.answers)
        progress = f"({answered + 1}/{total})"

        answer = f"{progress} **{next_q['display_name']}**\n{next_q['question']}"
        if next_q.get("hint"):
            answer += f"\n_{next_q['hint']}_"

        return {
            "answer":              answer,
            "collected_so_far":    session.answers,
            "questions_remaining": len(session.questions_remaining),
            "completed":           False,
        }

    return _run_knn_and_return(session, session_id)


def _run_knn_and_return(session: KNNSession, session_id: str) -> Dict[str, Any]:
    from certiq.forms import run_inference_from_form

    form_data = {
        attr_name: ans.get("value", "Yes")
        for attr_name, ans in session.answers.items()
    }

    result = run_inference_from_form(
        form_data=form_data,
        product_type_id=session.product_type_id,
        k=3,
        session_id=session_id,
    )

    session.result    = result
    session.completed = True

    return {
        "answer":    format_final_result(result),
        "result":    result,
        "completed": True,
    }


def format_final_result(result: Dict[str, Any]) -> str:
    """
    Formats the KNN result with BOTH time AND cost estimation.
    FIX: Added cost estimation. FIX: conf_emoji uses .get() — no KeyError.
    """
    if not result or "error" in result:
        return "❌ Could not generate estimate. Please try again."

    conf       = result.get("confidence", "LOW")
    conf_emoji = {"HIGH": "✅", "MEDIUM": "⚠️", "LOW": "❓"}.get(conf, "❓")
    neighbors  = result.get("k_neighbors", [])
    best       = neighbors[0] if neighbors else {}

    pred_hrs  = result.get("predicted_hrs", 0)
    est_cost  = round(pred_hrs * HOURLY_RATE_GBP)
    low_cost  = round(pred_hrs * HOURLY_RATE_GBP * 0.8)
    high_cost = round(pred_hrs * HOURLY_RATE_GBP * 1.25)

    lines = [
        "## 🏗️ Effort & Cost Estimate\n",
        "| | |",
        "|---|---|",
        f"| **Predicted Hours** | **{pred_hrs} hrs** |",
        f"| **Estimated Cost** | **£{est_cost:,}** |",
        f"| **Cost Range** | £{low_cost:,} – £{high_cost:,} |",
        f"| **Rate Used** | £{HOURLY_RATE_GBP:.0f}/hr |",
        f"| **Confidence** | {conf_emoji} {conf} |",
        f"| **Best Match** | {best.get('cert_id', '—')} at {best.get('similarity', 0)}% similarity |",
        f"| **Best Match Company** | {best.get('company', '—')} |",
        f"| **Historical Act Hrs** | {best.get('act_hrs', '—')} hrs |",
        f"| **Historical Variation** | {best.get('variation', 0):+.1f} hrs |",
        "",
        "### 📋 Similar Historical Certs\n",
        "| Cert | Company | Cert No | Similarity | Act Hrs | Est Cost | Variation |",
        "|------|---------|---------|------------|---------|----------|-----------|",
    ]

    for n in neighbors:
        bar        = "█" * int(n["similarity"] / 10)
        var_flag   = "🔴" if n["variation"] > 5 else "🟢" if n["variation"] < -5 else "🟡"
        company    = n.get("company") or "—"
        cert_no    = n.get("cert_no") or "—"
        cert_cost  = round(n["act_hrs"] * HOURLY_RATE_GBP)
        lines.append(
            f"| **{n['cert_id']}** "
            f"| {company[:22]} "
            f"| {cert_no} "
            f"| {n['similarity']}% {bar} "
            f"| **{n['act_hrs']} hrs** "
            f"| £{cert_cost:,} "
            f"| {var_flag} {n['variation']:+.1f}h |"
        )

    attrs   = result.get("extracted_attributes", {})
    present = [k.replace("_", " ").title() for k, v in attrs.items() if v.get("is_present")]
    absent  = [k.replace("_", " ").title() for k, v in attrs.items() if not v.get("is_present")]
    values  = {
        k.replace("_", " ").title(): v["value"]
        for k, v in attrs.items()
        if v.get("is_present") and v.get("value")
        and v["value"] not in ["Confirmed", "Present", "Yes"]
    }

    if present:
        lines.append(f"\n**✅ Attributes confirmed ({len(present)}/10):** {', '.join(present)}")
    if absent:
        lines.append(f"**❌ Not required ({len(absent)}/10):** {', '.join(absent)}")
    if values:
        lines.append("\n**📊 Extracted values:**")
        for k, v in values.items():
            lines.append(f"- **{k}:** {v}")

    lines.append(
        f"\n_Prediction based on KNN with Gower distance across historical certs. "
        f"Cost estimate uses £{HOURLY_RATE_GBP:.0f}/hr BBA certification rate. "
        f"Upload a PDF for a more precise attribute-level match._"
    )
    return "\n".join(lines)