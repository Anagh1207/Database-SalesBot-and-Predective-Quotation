import sqlite3
from typing import List, Dict, Any, Optional
from app.config import settings
from app.logger import get_logger

logger = get_logger("job_matcher")

DB_PATH = settings.DB_PATH

# Maps user keywords → exact prod_type strings from the jobs table
# All values verified against the actual timesheet data
# IMPORTANT: plasterboard only maps to genuinely relevant types —
# RE-Render and TB-Building Block removed because they pull outlier
# jobs with near-zero actual hours that skew the average badly
PRODUCT_KEYWORD_MAP = {
    "render":           ["RE - Render"],
    "plaster":          ["PP - Passive Fire Protection Sheet", "IW - Insulated Wall Lining"],
    "plasterboard":     ["PP - Passive Fire Protection Sheet", "IW - Insulated Wall Lining"],
    "board":            ["PP - Passive Fire Protection Sheet", "IW - Insulated Wall Lining",
                         "BQ - PVC-U Barge, Facia or Soffit Board"],
    "fire":             ["PP - Passive Fire Protection Sheet"],
    "fire resistance":  ["PP - Passive Fire Protection Sheet"],
    "passive fire":     ["PP - Passive Fire Protection Sheet"],
    "protection":       ["PP - Passive Fire Protection Sheet"],
    "wall lining":      ["IW - Insulated Wall Lining"],
    "lining":           ["IW - Insulated Wall Lining"],
    "cladding":         ["CL - Cladding", "CL"],
    "insulation":       ["RI - Roof Insulation", "EW - External Wall Insulation",
                         "FI - Floor Insulation", "IW - Insulated Wall Lining"],
    "wall insulation":  ["EW - External Wall Insulation", "IW - Insulated Wall Lining"],
    "roof insulation":  ["RI - Roof Insulation"],
    "floor insulation": ["FI - Floor Insulation"],
    "roof":             ["RI - Roof Insulation", "LA - Roofing (liquid-applied)",
                         "PT - Profiled Roofing Sheet", "RF - Roofing (roll form-bitumen)",
                         "RM - Roofing (roll form-miscellaneous)",
                         "RU - Built-up Metal Roofing", "SL - Roofing Slate", "RF"],
    "roofing":          ["LA - Roofing (liquid-applied)", "PT - Profiled Roofing Sheet",
                         "RF - Roofing (roll form-bitumen)", "RM - Roofing (roll form-miscellaneous)",
                         "RU - Built-up Metal Roofing", "SL - Roofing Slate", "RF"],
    "screed":           ["SC - Screed"],
    "wall tie":         ["WT - Wall Tie"],
    "tanking":          ["TA - Tanking"],
    "waterproof":       ["TA - Tanking", "DN - Damp-proof Course (new)"],
    "damp":             ["DN - Damp-proof Course (new)"],
    "drainage":         ["ID - Internal Drainage Membrane (wall)", "SW - Surface Water System"],
    "block":            ["TB - Building Block", "PK - Permanent Formwork"],
    "lintel":           ["LI - Lintel"],
    "window":           ["AF - Window and Door Hardware", "WI - Window System Supplier"],
    "door":             ["AF - Window and Door Hardware"],
    "mortar":           ["MO - Mortar"],
    "paint":            ["AC - Anti-corrosive Paint", "MP - Masonry Paint"],
    "rooflight":        ["RO - Rooflight"],
    "sheathing":        ["SG - Sheathing"],
    "pipe":             ["SP - Structured Wall Pipe and Fitting"],
    "sealing":          ["SS - Sealing Strip"],
    "strip":            ["SS - Sealing Strip"],
    "patch":            ["PU - Patch Repair Product"],
    "repair":           ["PU - Patch Repair Product"],
    "formwork":         ["PK - Permanent Formwork"],
    "slate":            ["SL - Roofing Slate"],
    "tile":             ["TU - Tile Substrate", "TU"],
    "gas":              ["GC - Gas Control Layer"],
    "membrane":         ["ID - Internal Drainage Membrane (wall)", "LA - Roofing (liquid-applied)"],
    "soil":             ["SR - Soil Reinforcement"],
    "water":            ["WX - Water Resisting Admixture", "SW - Surface Water System"],
    "infill":           ["IM - Infill wall panel"],
    "wall panel":       ["IM - Infill wall panel"],
    "soffit":           ["BQ - PVC-U Barge, Facia or Soffit Board"],
    "fascia":           ["BQ - PVC-U Barge, Facia or Soffit Board"],
    "barge":            ["BQ - PVC-U Barge, Facia or Soffit Board"],
}

# Broad fallback — used only when keyword search returns nothing at all
FALLBACK_PROD_TYPES = [
    "PP - Passive Fire Protection Sheet",
    "IW - Insulated Wall Lining",
    "RE - Render",
    "CL - Cladding",
    "EW - External Wall Insulation",
]


def _resolve_prod_types(keywords: List[str]) -> List[str]:
    """Converts user keywords into exact prod_type strings from the DB."""
    prod_types = []
    for keyword in keywords:
        keyword_lower = keyword.lower().strip()
        for map_key, types in PRODUCT_KEYWORD_MAP.items():
            if map_key in keyword_lower or keyword_lower in map_key:
                prod_types.extend(types)
    return list(set(prod_types))


def _filter_outliers(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Removes jobs where actual hours are less than 10% of estimated hours.
    These are abandoned, cancelled, or data-entry-error jobs that skew averages.
    Jobs with 0 estimated hours are kept as-is.
    """
    filtered = []
    for r in rows:
        est = r.get("est_hrs") or 0
        act = r.get("act_hrs") or 0
        if est <= 0:
            filtered.append(r)
        elif act / est >= 0.10:
            filtered.append(r)
        else:
            logger.info(f"Filtered outlier job {r.get('job_no')}: est={est}, act={act}")
    return filtered


def find_similar_jobs(
    prod_type_keywords: List[str] = None,
    job_type: str = None,
    max_results: int = 10,
    db_path: str = DB_PATH,
    fallback: bool = True,
) -> List[Dict[str, Any]]:
    """
    Finds similar historical jobs from the jobs table.

    Pass 1 — exact prod_type match via keyword map
    Pass 2 — LIKE search on raw keyword
    Pass 3 — broad fallback categories

    Outlier jobs (act_hrs < 10% of est_hrs) are filtered at every pass.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    def fetch_and_label(query: str, params: list) -> List[Dict[str, Any]]:
        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            r = dict(row)
            variation = r.get("variation") or 0
            r["variation_label"] = (
                f"+{variation} hrs (over)"   if variation > 0
                else f"{variation} hrs (under)" if variation < 0
                else "On budget"
            )
            results.append(r)
        return results

    rows = []

    # ── Pass 1: Exact match via keyword map ───────────────────────────────
    prod_types = _resolve_prod_types(prod_type_keywords or [])
    if prod_types:
        placeholders = ",".join("?" * len(prod_types))
        rows = fetch_and_label(
            f"SELECT * FROM jobs WHERE prod_type IN ({placeholders}) ORDER BY act_hrs DESC LIMIT ?",
            prod_types + [max_results * 2],
        )
        rows = _filter_outliers(rows)
        logger.info(f"Pass 1 (exact): {len(rows)} jobs after outlier filter")

    # ── Pass 2: LIKE search on raw keyword ────────────────────────────────
    if not rows and prod_type_keywords and fallback:
        like_conditions = " OR ".join("prod_type LIKE ?" for _ in prod_type_keywords)
        like_params = [f"%{kw}%" for kw in prod_type_keywords]
        rows = fetch_and_label(
            f"SELECT * FROM jobs WHERE {like_conditions} ORDER BY act_hrs DESC LIMIT ?",
            like_params + [max_results * 2],
        )
        rows = _filter_outliers(rows)
        logger.info(f"Pass 2 (LIKE): {len(rows)} jobs after outlier filter")

    # ── Pass 3: Broad fallback ─────────────────────────────────────────────
    if not rows and fallback:
        placeholders = ",".join("?" * len(FALLBACK_PROD_TYPES))
        rows = fetch_and_label(
            f"SELECT * FROM jobs WHERE prod_type IN ({placeholders}) ORDER BY act_hrs DESC LIMIT ?",
            FALLBACK_PROD_TYPES + [max_results * 2],
        )
        rows = _filter_outliers(rows)
        logger.info(f"Pass 3 (fallback): {len(rows)} jobs after outlier filter")

    conn.close()

    # Trim to max_results after filtering
    rows = rows[:max_results]

    logger.info(f"Job matcher returning {len(rows)} jobs for keywords: {prod_type_keywords}")
    return rows


def format_jobs_table(jobs: List[Dict[str, Any]]) -> str:
    """Formats job results as a markdown table."""
    if not jobs:
        return "No similar historical jobs found in the database."

    table  = "| Job No | Product Type | Job Type | Est. Hrs | Act. Hrs | Variation |\n"
    table += "|--------|-------------|----------|----------|----------|----------|\n"

    for job in jobs:
        table += (
            f"| {job.get('job_no', 'N/A')} "
            f"| {job.get('prod_type', 'N/A')} "
            f"| {job.get('job_type', 'N/A')} "
            f"| {job.get('est_hrs', 'N/A')} "
            f"| {job.get('act_hrs', 'N/A')} "
            f"| {job.get('variation_label', 'N/A')} |\n"
        )

    return table


def get_job_summary(jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Returns summary statistics for a list of similar jobs.
    Does NOT reference 'status' — that column does not exist in the timesheet.
    """
    if not jobs:
        return {
            "total_jobs":    0,
            "over_budget":   0,
            "under_budget":  0,
            "avg_est_hrs":   0,
            "avg_act_hrs":   0,
            "avg_variation": 0,
            "typical_range": "N/A",
        }

    total         = len(jobs)
    over_budget   = sum(1 for j in jobs if (j.get("variation") or 0) > 0)
    under_budget  = sum(1 for j in jobs if (j.get("variation") or 0) < 0)
    avg_est       = round(sum(j.get("est_hrs", 0) or 0 for j in jobs) / total, 1)
    avg_act       = round(sum(j.get("act_hrs", 0) or 0 for j in jobs) / total, 1)
    avg_variation = round(sum(j.get("variation", 0) or 0 for j in jobs) / total, 1)
    range_low     = max(0, round(avg_act - 10))
    range_high    = round(avg_act + 10)

    return {
        "total_jobs":    total,
        "over_budget":   over_budget,
        "under_budget":  under_budget,
        "avg_est_hrs":   avg_est,
        "avg_act_hrs":   avg_act,
        "avg_variation": avg_variation,
        "typical_range": f"{range_low}–{range_high} hrs",
    }