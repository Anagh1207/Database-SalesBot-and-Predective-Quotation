import sqlite3
import json
from typing import List, Dict, Any, Optional
from .data_loader import Chunk
from app.config import settings

DB_PATH = settings.DB_PATH


def init_db(db_path: str = DB_PATH):
    """
    Creates the SQLite database and chunks table.
    Safe to call multiple times — won't overwrite existing data.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id                    TEXT PRIMARY KEY,
            doc_id                      TEXT NOT NULL,
            window_id                   TEXT NOT NULL,
            page_start                  INTEGER,
            page_end                    INTEGER,
            text                        TEXT NOT NULL,
            technicality_score          REAL,
            product_names               TEXT,
            standards                   TEXT,
            constraints                 TEXT,
            functional_properties       TEXT,
            technical_entities          TEXT,
            performance_characteristics TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("✅ Database initialised at", db_path)


def insert_chunks(chunks: List[Chunk], db_path: str = DB_PATH):
    """
    Inserts all chunks into the database.
    Skips duplicates safely using INSERT OR IGNORE.
    """
    conn = sqlite3.connect(db_path)
    for c in chunks:
        conn.execute("""
            INSERT OR IGNORE INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            c.chunk_id,
            c.doc_id,
            c.window_id,
            c.page_start,
            c.page_end,
            c.text,
            c.technicality_score,
            json.dumps(c.product_names),
            json.dumps(c.standards),
            json.dumps(c.constraints),
            json.dumps(c.functional_properties),
            json.dumps(c.technical_entities),
            json.dumps(c.performance_characteristics),
        ))
    conn.commit()
    conn.close()
    print(f"✅ Inserted {len(chunks)} chunks into database")


def filter_chunks(
    doc_ids: List[str] = None,
    min_technicality: float = 0.0,
    standards_contain: str = None,
    db_path: str = DB_PATH,
) -> List[Dict[str, Any]]:
    """
    Filters chunks by structured metadata before vector search.
    Returns a list of matching rows as dictionaries.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    query = "SELECT * FROM chunks WHERE technicality_score >= ?"
    params = [min_technicality]

    if doc_ids:
        placeholders = ",".join("?" * len(doc_ids))
        query += f" AND doc_id IN ({placeholders})"
        params.extend(doc_ids)

    if standards_contain:
        query += " AND standards LIKE ?"
        params.append(f"%{standards_contain}%")

    rows = conn.execute(query, params).fetchall()
    conn.close()
    print(f"✅ Filter returned {len(rows)} candidate chunks")
    return [dict(row) for row in rows]