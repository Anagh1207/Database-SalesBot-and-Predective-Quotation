"""
certiq/inference.py

The bridge between the chatbot orchestrator and the KNN engine.

This is what gets called when the chatbot detects a KNN estimation
intent — it handles the full conversation flow:

  User message
       ↓
  Intent check (is this a KNN estimation request?)
       ↓
  Attribute extraction (from message OR by asking follow-up questions)
       ↓
  KNN prediction (certiq/knn.py)
       ↓
  Formatted response for the chatbot UI

Session state is kept in memory so multi-turn conversations work:
  Turn 1: "I need an estimate for a liquid applied roof"
  Turn 2: "It needs weathertightness and fire rating"
  Turn 3: "25 year durability, wind uplift resistance too"
  → System now has enough → runs KNN → returns estimate
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

from app.logger import get_logger
from certiq.store import get_attributes

logger = get_logger("certiq.inference")


# ══════════════════════════════════════════════════════════════════
# SESSION STATE — multi-turn conversation memory
# ══════════════════════════════════════════════════════════════════

@dataclass
class InferenceSession:
    session_id:       str
    product_type_id:  str                    = "LA"
    collected_attrs:  Dict[str, Any]         = field(default_factory=dict)
    turns:            int                    = 0
    prediction_shown: bool                   = False
    last_updated:     float                  = field(default_factory=time.time)

    def update_attrs(self, new_attrs: Dict[str, Any]):
        """Merges new attributes into collected set — True overrides False."""
        for k, v in new_attrs.items():
            if v or k not in self.collected_attrs:
                self.collected_attrs[k] = v
        self.turns       += 1
        self.last_updated = time.time()

    def active_attr_count(self) -> int:
        return sum(1 for v in self.collected_attrs.values() if v)

    def is_ready(self) -> bool:
        """
        Ready to predict when we have at least 3 active attributes
        OR the user has given input across 2+ turns.
        """
        return self.active_attr_count() >= 3 or (
            self.turns >= 2 and self.active_attr_count() >= 1
        )


# In-memory session store — keyed by session_id
_inference_sessions: Dict[str, InferenceSession] = {}

# Session TTL — 30 minutes
SESSION_TTL = 30 * 60


def _get_or_create_session(session_id: str, product_type_id: str = "LA") -> InferenceSession:
    _cleanup_old_sessions()
    if session_id not in _inference_sessions:
        _inference_sessions[session_id] = InferenceSession(
            session_id=session_id,
            product_type_id=product_type_id,
        )
    return _inference_sessions[session_id]


def _cleanup_old_sessions():
    now  = time.time()
    dead = [sid for sid, s in _inference_sessions.items()
            if now - s.last_updated > SESSION_TTL]
    for sid in dead:
        del _inference_sessions[sid]


# ══════════════════════════════════════════════════════════════════
# INTENT DETECTION
# ══════════════════════════════════════════════════════════════════

# Keywords that signal the user wants a KNN-based estimation
_KNN_TRIGGERS = [
    "estimate", "estimation", "predict", "how many hours", "hours for",
    "liquid applied", "liquid-applied", "roofing cert", "liquid roof",
    "weathertight", "fire rated", "wind uplift", "durability",
    "adhesion", "slip resistance", "noise", "root penetration",
    "knn", "similar jobs", "similar cert", "find similar",
    "how long will", "how long does", "time for cert",
]


def is_knn_estimation_query(message: str, session_id: str = None) -> bool:
    """
    Returns True if the message is a KNN estimation request
    OR if the session is already mid-estimation conversation.
    """
    msg_lower = message.lower()

    # Active session = always route to KNN flow
    if session_id and session_id in _inference_sessions:
        session = _inference_sessions[session_id]
        if not session.prediction_shown:
            return True

    # Keyword trigger
    return any(kw in msg_lower for kw in _KNN_TRIGGERS)


# ══════════════════════════════════════════════════════════════════
# MAIN INFERENCE HANDLER
# ══════════════════════════════════════════════════════════════════

def handle_knn_message(
    message: str,
    session_id: str  = None,
    product_type_id: str = "LA",
    k: int           = 3,
) -> Dict[str, Any]:
    """
    Main entry point. Called by the chatbot orchestrator.

    Handles multi-turn attribute collection and triggers KNN
    prediction when enough attributes are known.

    Returns dict compatible with ChatResponse fields:
      answer, prediction, sources, is_estimation
    """
    session_id = session_id or str(uuid.uuid4())
    session    = _get_or_create_session(session_id, product_type_id)

    logger.info(
        f"[KNN] session={session_id} | turn={session.turns + 1} | "
        f"message='{message[:60]}'"
    )

    # ── Extract attributes from this message ──────────────────────────────
    from certiq.forms import parse_chatbot_attrs
    new_attrs = parse_chatbot_attrs(message, product_type_id)
    session.update_attrs(new_attrs)

    logger.info(
        f"[KNN] Collected {session.active_attr_count()} active attrs "
        f"after turn {session.turns}"
    )

    # ── Decide: predict now or ask for more info ───────────────────────────
    if session.is_ready():
        return _run_prediction(session, k)
    else:
        return _ask_for_more(session, message)


def _run_prediction(session: InferenceSession, k: int) -> Dict[str, Any]:
    """Runs the KNN engine and formats the chatbot response."""
    try:
        from certiq.knn import get_estimation_engine

        engine = get_estimation_engine()
        result = engine.predict(
            input_attrs=session.collected_attrs,
            product_type_id=session.product_type_id,
            k=k,
            session_id=session.session_id,
            input_source="chatbot",
        )

        session.prediction_shown = True

        # ── Format chatbot answer ─────────────────────────────────────────
        hrs        = result["predicted_hrs"]
        confidence = result["confidence"]
        similar    = result["similar_jobs"]

        conf_emoji = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(confidence, "⚪")
        conf_text  = {"HIGH": "High confidence", "MEDIUM": "Medium confidence", "LOW": "Low confidence — limited similar certs"}.get(confidence, "")

        answer_lines = [
            f"## 📊 Estimation Result\n",
            f"**Predicted hours: {hrs}h** {conf_emoji} {conf_text}\n",
        ]

        # Attributes used
        active = [k for k, v in session.collected_attrs.items() if v]
        if active:
            attr_defs = {a["attr_name"]: a["display_name"] for a in get_attributes(session.product_type_id)}
            attr_display = [attr_defs.get(a, a) for a in active]
            answer_lines.append(f"**Attributes assessed:** {', '.join(attr_display)}\n")

        # Similar jobs table
        if similar:
            answer_lines.append("\n### Similar Jobs Used for This Estimate\n")
            answer_lines.append("| Cert | Company | Similarity | Est Hrs | Act Hrs | Variation |")
            answer_lines.append("|------|---------|-----------|---------|---------|-----------|")
            for job in similar:
                var   = job["variation"]
                var_s = f"+{var}h" if var >= 0 else f"{var}h"
                answer_lines.append(
                    f"| {job['cert_id']} "
                    f"| {job.get('company', 'Unknown')[:25]} "
                    f"| {job['similarity_pct']}% "
                    f"| {job['est_hrs']}h "
                    f"| {job['act_hrs']}h "
                    f"| {var_s} |"
                )

        # Explanation
        answer_lines.append(f"\n_{result['explanation']}_")

        # Follow-up prompt
        answer_lines.append(
            "\n\n💡 *Want to refine this estimate? Provide more attributes or upload a certificate PDF.*"
        )

        logger.info(
            f"[KNN] ✅ Predicted {hrs}h | confidence={confidence} | "
            f"session={session.session_id}"
        )

        return {
            "answer":       "\n".join(answer_lines),
            "prediction":   result,
            "is_estimation": True,
            "sources":      [],
            "jobs":         similar,
            "jobs_table":   _build_jobs_table(similar),
        }

    except Exception as e:
        logger.error(f"[KNN] Prediction failed: {e}", exc_info=True)
        return {
            "answer":       f"I encountered an error running the KNN estimate: {str(e)}. Please check the server logs.",
            "prediction":   None,
            "is_estimation": True,
            "sources":      [],
            "jobs":         [],
            "jobs_table":   "",
        }


def _ask_for_more(session: InferenceSession, message: str) -> Dict[str, Any]:
    """
    Not enough attributes yet — ask a targeted follow-up question.
    Identifies the most important missing attributes and asks about them.
    """
    attrs       = get_attributes(session.product_type_id)
    collected   = session.collected_attrs
    active      = [k for k, v in collected.items() if v]

    # Priority order — ask required/high-weight attrs first
    priority = [a for a in attrs if a.get("is_required") and a["attr_name"] not in active]
    secondary = [a for a in attrs if not a.get("is_required") and a["attr_name"] not in active]
    missing   = priority + secondary

    if session.turns == 1 and not active:
        # First turn and nothing extracted — broad ask
        answer = (
            "I can generate a KNN-based hour estimate for a **Roofing (Liquid-Applied)** certification job.\n\n"
            "To find the closest matching historical jobs, please tell me the technical requirements:\n\n"
            "- **Weathertightness** required? (Yes/No)\n"
            "- **Fire performance** required? (Yes/No)\n"
            "- **Wind uplift resistance** required? (Yes/No)\n"
            "- **Mechanical damage resistance** required? (Yes/No)\n"
            "- **Required service life** (e.g. 25 years)\n\n"
            "You can also just describe the job in one sentence and I'll extract the requirements automatically."
        )
    elif missing:
        # Ask about the top 3 most important missing attributes
        top_missing = missing[:3]
        questions   = [
            f"- **{a['display_name']}** — {a.get('form_hint', 'Yes / No')}"
            for a in top_missing
        ]
        active_display = []
        attr_map       = {a["attr_name"]: a["display_name"] for a in attrs}
        for attr_name in active:
            active_display.append(attr_map.get(attr_name, attr_name))

        collected_line = (
            f"✅ So far I have: **{', '.join(active_display)}**\n\n"
            if active_display else ""
        )
        answer = (
            f"{collected_line}"
            f"To improve the estimate, please confirm a few more requirements:\n\n"
            + "\n".join(questions)
            + "\n\n*Or say 'estimate now' to run with what I have.*"
        )
    else:
        # We have something, just run it
        return _run_prediction(session, k=3)

    return {
        "answer":        answer,
        "prediction":    None,
        "is_estimation": True,
        "sources":       [],
        "jobs":          [],
        "jobs_table":    "",
    }


def _build_jobs_table(similar_jobs: List[Dict]) -> str:
    """Builds a plain-text jobs table for the chatbot jobs_table field."""
    if not similar_jobs:
        return ""
    lines = [
        f"{'Cert':<8} {'Company':<25} {'Sim%':<6} {'Est':<6} {'Act':<6} {'Var'}",
        "-" * 65,
    ]
    for job in similar_jobs:
        var = job["variation"]
        lines.append(
            f"{job['cert_id']:<8} "
            f"{str(job.get('company',''))[:23]:<25} "
            f"{job['similarity_pct']:<6} "
            f"{job['est_hrs']:<6} "
            f"{job['act_hrs']:<6} "
            f"{var:+.1f}h"
        )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# DIRECT PREDICTION HELPERS (for the API router)
# ══════════════════════════════════════════════════════════════════

def predict_direct(
    input_attrs: Dict[str, Any],
    product_type_id: str = "LA",
    k: int               = 3,
    session_id: str      = None,
    input_source: str    = "api",
) -> Dict[str, Any]:
    """
    Runs the KNN engine directly with a known attribute dict.
    Used by knn_predict.py router (form, PDF endpoints).
    No session management needed — single-shot prediction.
    """
    from certiq.knn import get_estimation_engine
    session_id = session_id or str(uuid.uuid4())
    engine     = get_estimation_engine()
    return engine.predict(
        input_attrs=input_attrs,
        product_type_id=product_type_id,
        k=k,
        session_id=session_id,
        input_source=input_source,
    )


def clear_session(session_id: str):
    """Clears a session — call this when user starts a new conversation."""
    if session_id in _inference_sessions:
        del _inference_sessions[session_id]
        logger.info(f"[KNN] Session cleared: {session_id}")


def get_session_state(session_id: str) -> Optional[Dict[str, Any]]:
    """Returns current session state — useful for debugging."""
    session = _inference_sessions.get(session_id)
    if not session:
        return None
    return {
        "session_id":      session.session_id,
        "product_type_id": session.product_type_id,
        "turns":           session.turns,
        "active_attrs":    session.active_attr_count(),
        "collected_attrs": session.collected_attrs,
        "prediction_shown": session.prediction_shown,
        "is_ready":        session.is_ready(),
    }