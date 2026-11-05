# -*- coding: utf-8 -*-
"""SQL Guard: strict read-only execution, keyword validation, and safety limits."""

import re
import sqlite3
import time
from typing import Optional

FORBIDDEN_KEYWORDS = [
    r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b",
    r"\bALTER\b", r"\bATTACH\b", r"\bDETACH\b", r"\bPRAGMA\b",
    r"\bCREATE\b", r"\bVACUUM\b", r"\bEXEC\b", r"\bEXECUTE\b",
    r"\bTRUNCATE\b", r"\bREPLACE\b", r"\bMERGE\b"
]

def validate_sql(sql: str) -> tuple[bool, str]:
    """Validate that the query is strictly a read-only SELECT statement."""
    if not sql or not sql.strip():
        return False, "Empty SQL query."
        
    s = sql.strip().rstrip(";")
    
    # Check for multiple statements
    if ";" in s:
        return False, "Multiple SQL statements are not permitted."
        
    # Check start with SELECT or WITH
    s_upper = s.upper()
    if not (s_upper.startswith("SELECT") or s_upper.startswith("WITH")):
        return False, "Query must begin with SELECT or WITH."
        
    # Check forbidden keywords
    for pat in FORBIDDEN_KEYWORDS:
        if re.search(pat, s_upper):
            return False, f"Forbidden SQL keyword detected matching pattern: {pat}"
            
    return True, ""


def check_sql_syntax_and_schema(db_path: str, sql: str) -> tuple[bool, str]:
    """
    Pre-validate SQL query against SQLite schema using EXPLAIN to catch
    syntax errors, non-existent tables, and missing columns without full execution.
    """
    valid, err = validate_sql(sql)
    if not valid:
        return False, err
        
    s = sql.strip().rstrip(";")
    uri_path = f"file:{db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri_path, uri=True, timeout=5.0)
        conn.execute(f"EXPLAIN {s}")
        conn.close()
        return True, ""
    except sqlite3.OperationalError as e:
        return False, f"OperationalError: {str(e)}"
    except sqlite3.DatabaseError as e:
        return False, f"DatabaseError: {str(e)}"
    except Exception as e:
        return False, str(e)


def ensure_limit(sql: str, max_limit: int = 1000) -> str:
    """Ensure the SQL query has an appropriate LIMIT clause."""
    s = sql.strip().rstrip(";")
    match = re.search(r"\bLIMIT\s+(\d+)\b", s, re.IGNORECASE)
    if match:
        limit_val = int(match.group(1))
        if limit_val > max_limit:
            s = re.sub(r"\bLIMIT\s+\d+\b", f"LIMIT {max_limit}", s, flags=re.IGNORECASE)
        return s + ";"
    else:
        return f"{s} LIMIT {max_limit};"


def execute_safe_sql(
    db_path: str,
    sql: str,
    timeout_sec: float = 20.0
) -> tuple[bool, list[tuple], list[str], str]:
    """
    Execute SQL safely on a read-only SQLite database connection.
    Returns: (success, rows, column_names, error_message)
    """
    valid, err = validate_sql(sql)
    if not valid:
        return False, [], [], err
        
    guarded_sql = ensure_limit(sql, 1000)
    
    # Connect with read-only URI mode
    uri_path = f"file:{db_path}?mode=ro"
    
    start_time = time.time()
    try:
        conn = sqlite3.connect(uri_path, uri=True, timeout=timeout_sec)
        # Enable interrupt handler if query takes too long
        conn.set_progress_handler(
            lambda: 1 if (time.time() - start_time) > timeout_sec else 0,
            10000
        )
        cur = conn.cursor()
        cur.execute(guarded_sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        conn.close()
        return True, rows, cols, ""
    except sqlite3.OperationalError as e:
        return False, [], [], f"SQL OperationalError: {str(e)}"
    except sqlite3.DatabaseError as e:
        return False, [], [], f"SQL DatabaseError: {str(e)}"
    except Exception as e:
        return False, [], [], f"SQL Execution error: {str(e)}"
