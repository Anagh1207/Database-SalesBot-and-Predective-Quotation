"""
Prediction engine — takes job details, returns effort estimate.

Usage:
    from predictor.predict import predict_effort, find_similar_jobs
"""

import sqlite3
import pickle
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from app.config import settings
from app.logger import get_logger

logger = get_logger("predict")

DB_PATH    = settings.DB_PATH
MODEL_PATH = "data/predictor_model.pkl"
META_PATH  = "data/predictor_meta.pkl"

# Module-level cache
_model = None
_meta  = None


def load_model():
    """Loads model and meta from disk. Cached after first load."""
    global _model, _meta
    if _model is None:
        if not Path(MODEL_PATH).exists():
            raise FileNotFoundError(
                "Model not found. Run: python predictor/train.py"
            )
        with open(MODEL_PATH, "rb") as f:
            _model = pickle.load(f)
        with open(META_PATH, "rb") as f:
            _meta = pickle.load(f)
        logger.info(f"✅ Model loaded — CV MAE: ±{_meta['cv_mae']} hrs")
    return _model, _meta


def encode_input(
    prod_type: str,
    job_type:  str,
    est_hrs:   float,
    meta:      dict,
) -> np.ndarray:
    """
    Converts raw inputs into the feature vector the model expects.
    Handles unseen product/job types gracefully.
    """
    # Encode product type
    le_prod = meta["encoders"]["prod_type"]
    le_job  = meta["encoders"]["job_type"]

    if prod_type in le_prod.classes_:
        prod_enc = le_prod.transform([prod_type])[0]
    else:
        # Unknown product type — use median encoding
        prod_enc = len(le_prod.classes_) // 2
        logger.warning(f"Unknown product type: {prod_type} — using median encoding")

    if job_type in le_job.classes_:
        job_enc = le_job.transform([job_type])[0]
    else:
        job_enc = len(le_job.classes_) // 2
        logger.warning(f"Unknown job type: {job_type} — using median encoding")

    # Get product stats
    prod_stat = meta["prod_stats"].get(prod_type, {})
    job_stat  = meta["job_stats"].get(job_type, {})

    avg_price           = 0
    prod_avg_act_hrs    = prod_stat.get("avg_act_hrs",  est_hrs)
    prod_std_act_hrs    = prod_stat.get("std_act_hrs",  0)
    prod_count          = prod_stat.get("count",        1)
    prod_avg_overrun_pct= prod_stat.get("avg_overrun",  0)
    job_avg_act_hrs     = job_stat.get("avg_act_hrs",   est_hrs)

    features = np.array([[
        prod_enc,
        job_enc,
        est_hrs,
        avg_price,
        0,                    # sales_count — unknown for new jobs
        prod_avg_act_hrs,
        prod_std_act_hrs,
        prod_count,
        prod_avg_overrun_pct,
        job_avg_act_hrs,
    ]])

    return features


def predict_effort(
    prod_type: str,
    job_type:  str,
    est_hrs:   float = 40.0,
) -> Dict[str, Any]:
    """
    Main prediction function.

    Returns:
        predicted_hrs   - point estimate
        low_hrs         - lower bound (80% CI)
        high_hrs        - upper bound (80% CI)
        confidence_pct  - model confidence
        risk_flag       - HIGH / MEDIUM / LOW overrun risk
        risk_reason     - human readable explanation
        prod_stats      - historical stats for this product type
    """
    model, meta = load_model()

    features = encode_input(prod_type, job_type, est_hrs, meta)

    # Get predictions from all trees for uncertainty quantification
    tree_preds = np.array([
        tree.predict(features)[0]
        for tree in model.estimators_
    ])

    predicted  = float(np.mean(tree_preds))
    std_pred   = float(np.std(tree_preds))

    # 80% confidence interval
    low_hrs  = max(0, round(predicted - 1.28 * std_pred, 1))
    high_hrs = round(predicted + 1.28 * std_pred, 1)

    # Coefficient of variation — lower = more confident
    cv = std_pred / predicted if predicted > 0 else 1
    if cv < 0.2:
        confidence = "HIGH"
    elif cv < 0.4:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # Risk assessment from historical data
    prod_stat    = meta["prod_stats"].get(prod_type, {})
    overrun_rate = prod_stat.get("overrun_rate", 0.5)
    avg_overrun  = prod_stat.get("avg_overrun", 0)

    if overrun_rate > 0.7 or avg_overrun > 25:
        risk_flag   = "HIGH"
        risk_reason = f"{prod_type} jobs overrun {round(overrun_rate*100)}% of the time, averaging +{round(avg_overrun)}% over estimate"
    elif overrun_rate > 0.5 or avg_overrun > 10:
        risk_flag   = "MEDIUM"
        risk_reason = f"{prod_type} jobs have moderate overrun risk ({round(overrun_rate*100)}% overrun rate)"
    else:
        risk_flag   = "LOW"
        risk_reason = f"{prod_type} jobs generally come in on or under budget"

    return {
        "predicted_hrs":  round(predicted, 1),
        "low_hrs":        low_hrs,
        "high_hrs":       high_hrs,
        "confidence":     confidence,
        "risk_flag":      risk_flag,
        "risk_reason":    risk_reason,
        "prod_type":      prod_type,
        "job_type":       job_type,
        "est_hrs_input":  est_hrs,
        "prod_stats":     prod_stat,
        "cv_mae":         meta["cv_mae"],
    }


def find_similar_jobs(
    prod_type:  str,
    job_type:   str,
    max_results: int = 8,
    db_path:    str = DB_PATH,
) -> List[Dict[str, Any]]:
    """
    Finds the most similar historical jobs using KNN-style matching.

    Matching priority:
    1. Exact prod_type + job_type match (best)
    2. Exact prod_type match only
    3. Same job_type only (fallback)
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Try exact match first
    rows = conn.execute("""
        SELECT
            t.job_no,
            t.prod_type,
            t.job_type,
            t.est_hrs,
            t.act_hrs,
            t.variation,
            t.overrun_pct,
            t.status,
            COALESCE(s.customer_code, '') as customer_code,
            COALESCE(s.contract_price, 0) as contract_price,
            COALESCE(sl.cert_no, '')       as cert_no,
            1 as match_score
        FROM timesheet t
        LEFT JOIN sales s         ON t.prod_type = s.product_type
                                 AND t.job_type  = s.job_type
        LEFT JOIN sales_legacy sl ON t.job_no = sl.job_no
        WHERE t.prod_type = ? AND t.job_type = ?
        GROUP BY t.job_no
        ORDER BY ABS(t.variation) DESC
        LIMIT ?
    """, (prod_type, job_type, max_results)).fetchall()

    # If not enough exact matches — try prod_type only
    if len(rows) < 3:
        rows2 = conn.execute("""
            SELECT
                t.job_no,
                t.prod_type,
                t.job_type,
                t.est_hrs,
                t.act_hrs,
                t.variation,
                t.overrun_pct,
                t.status,
                COALESCE(s.customer_code, '') as customer_code,
                COALESCE(s.contract_price, 0) as contract_price,
                COALESCE(sl.cert_no, '')       as cert_no,
                2 as match_score
            FROM timesheet t
            LEFT JOIN sales s         ON t.prod_type = s.product_type
            LEFT JOIN sales_legacy sl ON t.job_no = sl.job_no
            WHERE t.prod_type = ?
              AND t.job_no NOT IN ({})
            GROUP BY t.job_no
            ORDER BY t.act_hrs DESC
            LIMIT ?
        """.format(",".join("?" * len(rows))),
            (prod_type, *[r["job_no"] for r in rows], max_results - len(rows))
        ).fetchall()
        rows = list(rows) + list(rows2)

    conn.close()

    results = []
    seen = set()
    for row in rows:
        r = dict(row)
        if r["job_no"] in seen:
            continue
        seen.add(r["job_no"])
        r["variation_label"] = (
            f"+{r['variation']}h (over)"  if r["variation"] > 0
            else f"{r['variation']}h (under)" if r["variation"] < 0
            else "On budget"
        )
        results.append(r)

    logger.info(f"Found {len(results)} similar jobs for {prod_type} / {job_type}")
    return results[:max_results]


def get_product_types(meta: dict = None) -> List[str]:
    """Returns all known product types."""
    if meta is None:
        _, meta = load_model()
    return sorted(meta["product_types"])


def get_job_types(meta: dict = None) -> List[str]:
    """Returns all known job types."""
    if meta is None:
        _, meta = load_model()
    return sorted(meta["job_types"])