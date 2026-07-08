"""
KNN Data Store — stores extracted attributes + job cost data.

Schema matches the boss's architecture diagram:
- cert_jobs: one row per cert, attributes + est/act hours
- inference_log: every live prediction logged

API is abstract — swap SQLite for PostgreSQL by changing DB_URL.
"""

import sqlite3
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from app.config import settings
from app.logger import get_logger

logger = get_logger("knn_store")
DB_PATH = settings.DB_PATH

# ── THE 10 ATTRIBUTES FOR ROOFING (liquid-applied) ────────────────────────
# These are the boss's exact attributes from Attributes and Match %.xlsx
ROOFING_ATTRIBUTES = [
    "weathertightness",
    "properties_in_relation_to_fire",
    "resistance_to_wind_uplift",
    "resistance_to_mechanical_damage",
    "resistance_to_penetration_of_roots",
    "durability",
    "protection_against_noise",
    "adhesion",
    "slip_resistance",
    "regulations",
]

ATTRIBUTE_DISPLAY_NAMES = {
    "weathertightness":                    "Weathertightness",
    "properties_in_relation_to_fire":      "Properties in relation to fire",
    "resistance_to_wind_uplift":           "Resistance to wind uplift",
    "resistance_to_mechanical_damage":     "Resistance to mechanical damage",
    "resistance_to_penetration_of_roots":  "Resistance to penetration of roots",
    "durability":                          "Durability",
    "protection_against_noise":            "Protection against noise",
    "adhesion":                            "Adhesion",
    "slip_resistance":                     "Slip Resistance",
    "regulations":                         "Regulations",
}


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def setup_knn_tables(db_path: str = DB_PATH):
    """
    Creates all KNN store tables.
    Safe to run multiple times — uses IF NOT EXISTS.
    """
    conn = get_connection(db_path)

    # ── PRODUCT TYPES ──────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knn_product_types (
            product_type_id   TEXT PRIMARY KEY,
            display_name      TEXT NOT NULL,
            description       TEXT,
            created_at        TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── ATTRIBUTE DEFINITIONS ──────────────────────────────────────────────
    # One row per attribute per product type
    # This is what makes the system dynamic — add new attributes here
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knn_attributes (
            attr_id           TEXT PRIMARY KEY,
            product_type_id   TEXT NOT NULL,
            attr_name         TEXT NOT NULL,
            display_name      TEXT NOT NULL,
            data_type         TEXT DEFAULT 'boolean',
            unit              TEXT,
            weight            REAL DEFAULT 1.0,
            is_required       INTEGER DEFAULT 0,
            search_keywords   TEXT,   -- JSON array
            form_question     TEXT,   -- what to ask the user
            form_hint         TEXT,   -- e.g. "e.g. 25 years, Class B"
            created_at        TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── KNN DATA STORE ─────────────────────────────────────────────────────
    # One row per cert document — combined labelled dataset
    # Attributes stored as JSON for flexibility
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knn_cert_jobs (
            job_id            TEXT PRIMARY KEY,
            product_type_id   TEXT NOT NULL,
            cert_id           TEXT,
            cert_no           TEXT,
            company           TEXT,
            product_name      TEXT,
            pdf_path          TEXT,
            attributes        TEXT NOT NULL,  -- JSON: {attr_name: value}
            attr_vector       TEXT,           -- JSON: [0,1,1,0,...] for KNN
            est_hrs           REAL,
            act_hrs           REAL,
            variation         REAL,
            ingested_at       TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── INFERENCE LOG ──────────────────────────────────────────────────────
    # Every live prediction logged here — feeds future training
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knn_inference_log (
            log_id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id        TEXT,
            product_type_id   TEXT,
            input_attributes  TEXT,   -- JSON: what user provided
            input_source      TEXT,   -- chatbot/form/pdf/email
            k_neighbors       INTEGER,
            matched_jobs      TEXT,   -- JSON: [{job_id, distance, est_hrs}]
            predicted_hrs     REAL,
            confidence        TEXT,
            created_at        TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    logger.info("✅ KNN store tables created")


def seed_roofing_product_type(db_path: str = DB_PATH):
    """Seeds the Roofing (liquid-applied) product type and its 10 attributes."""
    conn = get_connection(db_path)

    conn.execute("""
        INSERT OR IGNORE INTO knn_product_types
        (product_type_id, display_name, description)
        VALUES (?, ?, ?)
    """, ("LA", "Roofing (liquid-applied)",
          "Liquid-applied waterproofing systems for flat and pitched roofs"))

    ATTRIBUTES = [
        {
            "attr_id":        "LA_001",
            "attr_name":      "weathertightness",
            "display_name":   "Weathertightness",
            "data_type":      "boolean",
            "weight":         2.0,
            "is_required":    1,
            "search_keywords":["weathertight", "weather tight", "resist the passage of moisture",
                               "waterproof", "water resistance", "moisture penetration"],
            "form_question":  "Does this job require weathertightness assessment?",
            "form_hint":      "Yes / No",
        },
        {
            "attr_id":        "LA_002",
            "attr_name":      "properties_in_relation_to_fire",
            "display_name":   "Properties in relation to fire",
            "data_type":      "boolean",
            "weight":         2.0,
            "is_required":    1,
            "search_keywords":["fire", "reaction to fire", "fire resistance", "bs en 13501",
                               "euroclass", "broof", "froof", "properties in relation to fire"],
            "form_question":  "Is fire performance assessment required?",
            "form_hint":      "Yes / No",
        },
        {
            "attr_id":        "LA_003",
            "attr_name":      "resistance_to_wind_uplift",
            "display_name":   "Resistance to wind uplift",
            "data_type":      "boolean",
            "weight":         1.5,
            "is_required":    0,
            "search_keywords":["wind uplift", "wind suction", "wind load",
                               "resistance to wind", "uplift pressure"],
            "form_question":  "Is wind uplift resistance required?",
            "form_hint":      "Yes / No",
        },
        {
            "attr_id":        "LA_004",
            "attr_name":      "resistance_to_mechanical_damage",
            "display_name":   "Resistance to mechanical damage",
            "data_type":      "boolean",
            "weight":         1.5,
            "is_required":    0,
            "search_keywords":["mechanical damage", "foot traffic", "pedestrian",
                               "impact resistance", "structural movement",
                               "resistance to mechanical"],
            "form_question":  "Is resistance to mechanical damage required?",
            "form_hint":      "e.g. pedestrian access, maintenance traffic",
        },
        {
            "attr_id":        "LA_005",
            "attr_name":      "resistance_to_penetration_of_roots",
            "display_name":   "Resistance to penetration of roots",
            "data_type":      "boolean",
            "weight":         1.0,
            "is_required":    0,
            "search_keywords":["root", "roots", "root penetration",
                               "green roof", "vegetation", "fll"],
            "form_question":  "Is root penetration resistance required (green roof)?",
            "form_hint":      "Yes / No — only relevant for green roof applications",
        },
        {
            "attr_id":        "LA_006",
            "attr_name":      "durability",
            "display_name":   "Durability",
            "data_type":      "numeric",
            "unit":           "years",
            "weight":         2.0,
            "is_required":    1,
            "search_keywords":["durability", "service life", "design life",
                               "at least.*years", "years.*service"],
            "form_question":  "What is the required service life?",
            "form_hint":      "e.g. 10 years, 25 years",
        },
        {
            "attr_id":        "LA_007",
            "attr_name":      "protection_against_noise",
            "display_name":   "Protection against noise",
            "data_type":      "boolean",
            "weight":         0.8,
            "is_required":    0,
            "search_keywords":["noise", "sound", "acoustic", "sound reduction",
                               "airborne sound", "protection against noise"],
            "form_question":  "Is acoustic performance assessment required?",
            "form_hint":      "Yes / No",
        },
        {
            "attr_id":        "LA_008",
            "attr_name":      "adhesion",
            "display_name":   "Adhesion",
            "data_type":      "boolean",
            "weight":         1.5,
            "is_required":    0,
            "search_keywords":["adhesion", "bond", "bonding", "bond strength",
                               "pull-off", "peel", "adhesion.*substrate"],
            "form_question":  "Is adhesion testing required?",
            "form_hint":      "Yes / No",
        },
        {
            "attr_id":        "LA_009",
            "attr_name":      "slip_resistance",
            "display_name":   "Slip Resistance",
            "data_type":      "boolean",
            "weight":         1.0,
            "is_required":    0,
            "search_keywords":["slip", "slip resistance", "coefficient of friction",
                               "anti-slip", "pendulum test", "ramp test"],
            "form_question":  "Is slip resistance assessment required?",
            "form_hint":      "Yes / No — relevant for pedestrian access areas",
        },
        {
            "attr_id":        "LA_010",
            "attr_name":      "regulations",
            "display_name":   "Regulations",
            "data_type":      "boolean",
            "weight":         1.5,
            "is_required":    1,
            "search_keywords":["building regulations", "approved document",
                               "schedule 1", "nhbc", "bs en", "compliance",
                               "regulatory", "part b", "part c", "part l"],
            "form_question":  "Which building regulations apply?",
            "form_hint":      "e.g. Building Regs Part B, NHBC, BS EN 13501",
        },
    ]

    for attr in ATTRIBUTES:
        conn.execute("""
            INSERT OR IGNORE INTO knn_attributes
            (attr_id, product_type_id, attr_name, display_name, data_type,
             unit, weight, is_required, search_keywords, form_question, form_hint)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            attr["attr_id"], "LA",
            attr["attr_name"], attr["display_name"],
            attr["data_type"], attr.get("unit", ""),
            attr["weight"], attr["is_required"],
            json.dumps(attr["search_keywords"]),
            attr["form_question"], attr.get("form_hint", ""),
        ))

    conn.commit()
    conn.close()
    logger.info("✅ Roofing (LA) product type and 10 attributes seeded")


def get_attributes(product_type_id: str, db_path: str = DB_PATH) -> List[Dict]:
    """Returns all attributes for a product type ordered by weight."""
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT * FROM knn_attributes
        WHERE product_type_id = ?
        ORDER BY weight DESC, attr_name ASC
    """, (product_type_id,)).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["search_keywords"] = json.loads(d["search_keywords"] or "[]")
        result.append(d)
    return result


def upsert_cert_job(job: Dict[str, Any], db_path: str = DB_PATH):
    """Inserts or updates a cert job in the KNN store."""
    conn = get_connection(db_path)
    conn.execute("""
        INSERT OR REPLACE INTO knn_cert_jobs
        (job_id, product_type_id, cert_id, cert_no, company,
         product_name, pdf_path, attributes, attr_vector,
         est_hrs, act_hrs, variation)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        job["job_id"], job["product_type_id"],
        job.get("cert_id", ""), job.get("cert_no", ""),
        job.get("company", ""), job.get("product_name", ""),
        job.get("pdf_path", ""),
        json.dumps(job["attributes"]),
        json.dumps(job.get("attr_vector", [])),
        job["est_hrs"], job["act_hrs"],
        job["act_hrs"] - job["est_hrs"],
    ))
    conn.commit()
    conn.close()


def get_all_cert_jobs(product_type_id: str = "LA",
                      db_path: str = DB_PATH) -> List[Dict]:
    """Returns all cert jobs for KNN inference."""
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT * FROM knn_cert_jobs
        WHERE product_type_id = ?
        ORDER BY job_id
    """, (product_type_id,)).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["attributes"]  = json.loads(d["attributes"]  or "{}")
        d["attr_vector"] = json.loads(d["attr_vector"] or "[]")
        result.append(d)
    return result


def log_inference(log: Dict[str, Any], db_path: str = DB_PATH):
    """Logs a live inference to the inference_log table."""
    conn = get_connection(db_path)
    conn.execute("""
        INSERT INTO knn_inference_log
        (session_id, product_type_id, input_attributes,
         input_source, k_neighbors, matched_jobs,
         predicted_hrs, confidence)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        log.get("session_id", ""),
        log.get("product_type_id", "LA"),
        json.dumps(log.get("input_attributes", {})),
        log.get("input_source", "chatbot"),
        log.get("k_neighbors", 3),
        json.dumps(log.get("matched_jobs", [])),
        log.get("predicted_hrs", 0),
        log.get("confidence", "LOW"),
    ))
    conn.commit()
    conn.close()