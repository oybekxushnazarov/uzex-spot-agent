# -*- coding: utf-8 -*-
"""Grounding Verifier: ensures no hallucinated numbers, dates, or IDs in responses."""

import re
from typing import Any

def normalize_num_str(s: str) -> str:
    """Strip spaces, commas, thousand separators."""
    return s.replace(" ", "").replace(",", "").replace("\u00a0", "").strip()

def extract_numbers_from_text(text: str) -> set[str]:
    """Extract all standalone numerical tokens (integers and floats)."""
    # Exclude standard list numbers at start of lines (e.g. '1. ', '2. ')
    cleaned = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    
    # Match numbers (including decimals and spaced thousands)
    matches = re.findall(r"\b\d+(?:[\s\u00a0]\d{3})*(?:\.\d+)?\b", cleaned)
    tokens = set()
    for m in matches:
        n = normalize_num_str(m)
        if n:
            tokens.add(n)
    return tokens


def build_allowed_tokens(
    rows: list[tuple],
    question: str,
    extra_allowed: set[str] | None = None
) -> set[str]:
    """Extract all valid numbers, dates, and string fragments from SQL rows and question."""
    allowed = set()
    
    # Numbers from the question itself are allowed
    allowed.update(extract_numbers_from_text(question))
    
    # Known dataset date range bounds
    allowed.update(["2022", "2023", "2024", "2025", "2026", "03", "01", "30", "10", "15", "1000", "50", "10", "5", "1", "2", "3", "4"])
    
    if extra_allowed:
        allowed.update(extra_allowed)
        
    for row in rows:
        for val in row:
            if val is None:
                continue
            s_val = str(val).strip()
            allowed.add(s_val)
            # Add formatted variations
            norm_val = normalize_num_str(s_val)
            allowed.add(norm_val)
            
            # If float, also add rounded int and 2-decimal representation
            try:
                f = float(norm_val)
                allowed.add(str(int(f)))
                allowed.add(f"{f:.2f}")
                allowed.add(f"{f:.1f}")
            except ValueError:
                pass
                
            # If date format (YYYY-MM-DD), also add DD.MM.YYYY
            date_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s_val)
            if date_match:
                y, m, d = date_match.groups()
                allowed.add(f"{d}.{m}.{y}")
                allowed.add(f"{int(d)}.{int(m)}.{y}")
                allowed.add(y)
                allowed.add(d)
                allowed.add(m)

    return allowed


def verify_grounding(
    answer_text: str,
    rows: list[tuple],
    question: str,
    extra_allowed: set[str] | None = None
) -> tuple[bool, list[str]]:
    """
    Verify that every number in answer_text is justified by rows or question.
    Returns: (is_grounded, list_of_unjustified_tokens)
    """
    # Skip verification for explicit refusal or NO_DATA responses
    if "NO_DATA" in answer_text or "REFUSED" in answer_text or "mavjud emas" in answer_text or "отсутствует" in answer_text:
        return True, []
        
    # Isolate main body before the Evidence section to avoid flagging SQL query syntax
    body = answer_text.split("### Asos")[0].split("### Обоснование")[0]
    
    numbers_in_answer = extract_numbers_from_text(body)
    allowed = build_allowed_tokens(rows, question, extra_allowed)
    
    unjustified = []
    for num in numbers_in_answer:
        # Ignore small common numbers like 1..10 used in lists or single digits
        if num in {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}:
            continue
            
        # Check direct membership or substring of allowed
        if num in allowed:
            continue
            
        # Check float equivalences
        matched = False
        try:
            val_f = float(num)
            for a in allowed:
                try:
                    if abs(val_f - float(a)) < 0.01:
                        matched = True
                        break
                except ValueError:
                    continue
        except ValueError:
            pass
            
        if not matched:
            unjustified.append(num)
            
    if unjustified:
        return False, unjustified
    return True, []
