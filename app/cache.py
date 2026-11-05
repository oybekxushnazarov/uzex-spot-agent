# -*- coding: utf-8 -*-
"""Cache for successful pipeline results (normalized question -> SQL + answer)."""

import os
import re
import sqlite3
import time
from typing import Optional, Any

CACHE_DB_PATH = os.environ.get("UZEX_CACHE_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "cache.db")))

def normalize_query_key(query: str) -> str:
    """Normalize query string for consistent caching."""
    q = query.lower().strip()
    q = re.sub(r"[?!.,;:\"'«»]+$", "", q).strip()
    q = re.sub(r"\s+", " ", q)
    return q

def init_cache_db():
    os.makedirs(os.path.dirname(CACHE_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(CACHE_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_cache (
            query_norm TEXT PRIMARY KEY,
            lang TEXT NOT NULL,
            sql TEXT NOT NULL,
            answer TEXT NOT NULL,
            plan TEXT NOT NULL,
            definition TEXT NOT NULL,
            rows_count INTEGER NOT NULL,
            sample_deal_ids TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# Initialize on import
init_cache_db()

def get_cached_result(query: str, lang: str) -> Optional[dict[str, Any]]:
    """Retrieve cached successful pipeline result."""
    q_norm = normalize_query_key(query)
    try:
        conn = sqlite3.connect(CACHE_DB_PATH, timeout=2.0)
        cur = conn.cursor()
        cur.execute(
            "SELECT lang, sql, answer, plan, definition, rows_count, sample_deal_ids FROM pipeline_cache WHERE query_norm = ?",
            (q_norm,)
        )
        row = cur.fetchone()
        conn.close()
        if row:
            import json
            return {
                "lang": row[0],
                "sql": row[1],
                "answer": row[2],
                "plan": row[3],
                "definition": row[4],
                "rows_count": row[5],
                "sample_deal_ids": json.loads(row[6]) if row[6] else []
            }
    except Exception as e:
        print(f"[Cache Warning] Failed to read cache: {e}")
    return None

def set_cached_result(
    query: str,
    lang: str,
    sql: str,
    answer: str,
    plan: str,
    definition: str,
    rows_count: int,
    sample_deal_ids: list[Any]
):
    """Save a successful pipeline execution. Never call this on failure or errors."""
    q_norm = normalize_query_key(query)
    try:
        import json
        conn = sqlite3.connect(CACHE_DB_PATH, timeout=5.0)
        conn.execute("""
            INSERT OR REPLACE INTO pipeline_cache 
            (query_norm, lang, sql, answer, plan, definition, rows_count, sample_deal_ids, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            q_norm,
            lang,
            sql,
            answer,
            plan,
            definition,
            rows_count,
            json.dumps(sample_deal_ids),
            time.time()
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Cache Warning] Failed to write cache: {e}")
