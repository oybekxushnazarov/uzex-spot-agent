# -*- coding: utf-8 -*-
"""Deterministic entity resolution (pre-LLM and local pipeline)."""

import re
import sqlite3
from typing import Optional, Any
from app.dictionaries import (
    TN_VED_PRODUCTS, REGION_ALIASES, DATA_DATE_MIN, DATA_DATE_MAX,
    DEAL_ID_MIN, DEAL_ID_MAX
)

# Out-of-data keyword triggers
OUT_OF_DATA_COMMODITIES = [
    "золот", "oltin", "gold", "серебр", "kumush", "silver",
    "автомобил", "avtomobil", "car", "mashina", "платин", "platina"
]

OUT_OF_DATA_FIELDS = [
    "директор", "director", "direktor", "директоры", "rahbar", "руководител",
    "телефон", "telefon", "phone", "паспорт", "pasport", "манзил",
    "uy manzili", "личный номер", "boshliq"
]

OUT_OF_DATA_FORECASTS = [
    "прогноз", "prognoz", "kutilmoqda", "kelajak", "forecast", "predict",
    "2027", "2028", "2029", "2030"
]

_CYR_TO_LAT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l',
    'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's',
    'т': 't', 'у': 'u', 'ф': 'f', 'х': 'x', 'ц': 'ts', 'ч': 'ch',
    'ш': 'sh', 'щ': 'sh', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e',
    'ю': 'yu', 'я': 'ya', 'ё': 'yo',
    'қ': 'q', 'ғ': 'g', 'ҳ': 'h', 'ў': 'o',
}

def to_latin_key(name: str) -> str:
    s = name.lower()
    res = []
    for ch in s:
        res.append(_CYR_TO_LAT_MAP.get(ch, ch))
    res_str = "".join(res)
    return re.sub(r"[^a-z0-9]", "", res_str)


def resolve_entities(text: str, conn: sqlite3.Connection) -> dict[str, Any]:
    """Extract deterministic entities from the query."""
    res = {
        "deal_id": None,
        "contract_id": None,
        "inn": None,
        "broker_code": None,
        "tn_ved": None,
        "tn_ved_info": None,
        "region_uz": None,
        "year": None,
        "date_iso": None,
        "is_out_of_data": False,
        "out_of_data_reason": "",
        "company_candidates": [],
        "trap_type": None,
    }
    
    t = text.lower()
    
    # 1. Out of data checks
    for kw in OUT_OF_DATA_COMMODITIES:
        if kw in t:
            res["is_out_of_data"] = True
            res["trap_type"] = "trap_no_product"
            res["out_of_data_reason"] = f"Commodity '{kw}' is not traded on UZEX (dataset contains 40 specific commodity codes)."
            return res
            
    for kw in OUT_OF_DATA_FIELDS:
        if kw in t:
            res["is_out_of_data"] = True
            res["trap_type"] = "trap_no_field"
            res["out_of_data_reason"] = "Director names, personal phones, and private data are not present in the dataset."
            return res
            
    for kw in OUT_OF_DATA_FORECASTS:
        if kw in t:
            res["is_out_of_data"] = True
            res["trap_type"] = "trap_forecast"
            res["out_of_data_reason"] = f"Forecasts and future data are not available. Dataset covers 03.01.2022 to 30.10.2026."
            return res

    # 2. Extract 9-digit INN
    inn_match = re.search(r"\b(\d{9})\b", text)
    if inn_match:
        res["inn"] = inn_match.group(1)
        
    # 3. Extract broker code
    broker_match = re.search(r"\b(BK\d{3})\b", text, re.IGNORECASE)
    if broker_match:
        res["broker_code"] = broker_match.group(1).upper()
        
    # 4. Extract deal ID (6 digits usually 100001..604956)
    # Check for phrases like "сделка номер 123456", "сделку 123456", "123456-raqamli bitim", "deal 123456"
    deal_match = re.search(r"(?:сделк[а-я]*|bitim[a-z]*|номер[а-я]*|raqam[a-z]*|deal)?\s*#?\s*([1-9]\d{5})\b", text, re.IGNORECASE)
    if deal_match and not res["inn"]:
        val = int(deal_match.group(1))
        # If val looks like a deal ID
        if val > 604956 or val < 100001:
            res["deal_id"] = val
            res["is_out_of_data"] = True
            res["trap_type"] = "trap_no_data"
            res["out_of_data_reason"] = f"Deal ID {val} is outside the valid range (100001 - 604956)."
            return res
        else:
            # Check existence in database
            cur = conn.cursor()
            cur.execute("SELECT deal_id FROM deals WHERE deal_id = ?", (val,))
            if cur.fetchone():
                res["deal_id"] = val
            else:
                res["deal_id"] = val
                res["is_out_of_data"] = True
                res["trap_type"] = "trap_missing_id"
                res["out_of_data_reason"] = f"Deal ID {val} does not exist in the database (numbering gap)."
                return res

    # 5. Extract contract ID if mentioned
    contract_match = re.search(r"(?:контракт[а-я]*|shartnoma[a-z]*)\s*#?\s*(\d{6})\b", text, re.IGNORECASE)
    if contract_match:
        res["contract_id"] = contract_match.group(1)

    # 6. Extract date (DD.MM.YYYY or DD-MM-YYYY or named month)
    date_match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", text)
    if date_match:
        d, m, y = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
        iso = f"{y:04d}-{m:02d}-{d:02d}"
        if iso < DATA_DATE_MIN or iso > DATA_DATE_MAX:
            res["is_out_of_data"] = True
            res["trap_type"] = "trap_date_range"
            res["out_of_data_reason"] = f"Date {iso} is outside dataset boundaries ({DATA_DATE_MIN} to {DATA_DATE_MAX})."
            return res
        res["date_iso"] = iso

    # Month words in text (e.g. "15 июня 2024", "2024 yil 15 iyun")
    month_map = {
        "январ": "01", "yanvar": "01",
        "феврал": "02", "fevral": "02",
        "март": "03", "mart": "03",
        "апрел": "04", "aprel": "04",
        "май": "05", "may": "05",
        "июн": "06", "iyun": "06",
        "июл": "07", "iyul": "07",
        "август": "08", "avgust": "08",
        "сентябр": "09", "sentabr": "09", "sentyabr": "09",
        "октябр": "10", "oktabr": "10", "oktyabr": "10",
        "ноябр": "11", "noyabr": "11",
        "декабр": "12", "dekabr": "12"
    }
    for m_kw, m_num in month_map.items():
        m_regex = re.search(rf"\b(\d{{1,2}})\s+{m_kw}[a-zа-я]*\s+(\d{{4}})\b", text, re.IGNORECASE)
        if m_regex:
            d_val = int(m_regex.group(1))
            y_val = int(m_regex.group(2))
            iso = f"{y_val:04d}-{m_num}-{d_val:02d}"
            if iso < DATA_DATE_MIN or iso > DATA_DATE_MAX:
                res["is_out_of_data"] = True
                res["trap_type"] = "trap_date_range"
                res["out_of_data_reason"] = f"Date {iso} is outside dataset boundaries ({DATA_DATE_MIN} to {DATA_DATE_MAX})."
                return res
            res["date_iso"] = iso
            break
            
        m_regex2 = re.search(rf"\b(\d{{4}})\s+yil\s+(\d{{1,2}})\s+{m_kw}[a-zа-я]*\b", text, re.IGNORECASE)
        if m_regex2:
            y_val = int(m_regex2.group(1))
            d_val = int(m_regex2.group(2))
            iso = f"{y_val:04d}-{m_num}-{d_val:02d}"
            if iso < DATA_DATE_MIN or iso > DATA_DATE_MAX:
                res["is_out_of_data"] = True
                res["trap_type"] = "trap_date_range"
                res["out_of_data_reason"] = f"Date {iso} is outside dataset boundaries ({DATA_DATE_MIN} to {DATA_DATE_MAX})."
                return res
            res["date_iso"] = iso
            break

    # 7. Extract Year
    year_match = re.search(r"\b(202[2-6])\b", text)
    if year_match:
        res["year"] = int(year_match.group(1))

    # 8. Match TN VED Commodity
    matched_tn = None
    longest_match_len = 0
    for code, info in TN_VED_PRODUCTS.items():
        for syn in info["synonyms"]:
            syn_lower = syn.lower()
            # If short <= 3 chars ("un", "gaz"), require full boundary; else prefix match to catch inflections
            if len(syn_lower) <= 3:
                pattern = rf"\b{re.escape(syn_lower)}\b"
            else:
                pattern = rf"\b{re.escape(syn_lower)}"
            if re.search(pattern, t):
                if len(syn_lower) > longest_match_len:
                    longest_match_len = len(syn_lower)
                    matched_tn = code
    # Also check common root forms
    if not matched_tn:
        if re.search(r"\bхлопк", t):
            matched_tn = "520100"
        elif re.search(r"\bсахар", t):
            matched_tn = "170199"
        elif re.search(r"\bцемент", t):
            matched_tn = "252329"
        elif re.search(r"\bбензин", t):
            matched_tn = "271012"
        elif re.search(r"\bпшениц", t):
            matched_tn = "100199"
            
    if matched_tn:
        res["tn_ved"] = matched_tn
        res["tn_ved_info"] = TN_VED_PRODUCTS[matched_tn]

    # 9. Match Region
    for r_alias, canonical in REGION_ALIASES.items():
        if re.search(rf"\b{re.escape(r_alias)}\b", t):
            # Special care: if text has both "шахри" and "вилояти"
            if "toshkent shahri" in t or "город ташкент" in t or "г. ташкент" in t:
                res["region_uz"] = "Toshkent shahri"
            elif "toshkent viloyati" in t or "ташкентская область" in t:
                res["region_uz"] = "Toshkent viloyati"
            else:
                res["region_uz"] = canonical
            break

    return res
