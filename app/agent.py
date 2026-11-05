# -*- coding: utf-8 -*-
"""Master Agent orchestrating entity resolution, LLM planning, guard, execution, and grounding."""

import json
import os
import re
import sqlite3
import time
from typing import Any, Optional

from app.dictionaries import DATA_DATE_MIN, DATA_DATE_MAX
from app.lang_detect import detect_language, check_injection, is_empty_or_spam
from app.entity_resolver import resolve_entities
from app.schema_prompt import SCHEMA_PROMPT
from app.llm import call_llm_chain
from app.sql_guard import execute_safe_sql, validate_sql, check_sql_syntax_and_schema
from app.renderer import format_number, render_evidence_block, render_table_or_rows
from app.verifier import verify_grounding
from app.cache import get_cached_result, set_cached_result

DB_PATH = os.environ.get("UZEX_DB_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "uzex.db")))
LOGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "logs"))

# Conversational session memory (last 2 turns per session_id)
SESSION_MEMORY: dict[str, list[dict[str, Any]]] = {}


def log_query(record: dict[str, Any]):
    """Append structured JSON log entry."""
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        log_file = os.path.join(LOGS_DIR, "queries.jsonl")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def execute_plan_and_render(
    plan_dict: dict[str, Any],
    question: str,
    lang: str,
    db_path: str = DB_PATH
) -> tuple[str, bool, dict[str, Any]]:
    """
    Execute SQL from plan, format answer, verify grounding, and render Evidence block.
    Returns: (final_answer, is_grounded, metadata)
    """
    sql = plan_dict.get("sql", "").strip()
    plan_desc = plan_dict.get("plan", "")
    template = plan_dict.get("answer_template", "")
    definition = plan_dict.get("definition", "Без аннулированных сделок" if lang == "ru" else "Bekor qilingan bitimlar bundan mustasno")
    
    # Check for empty / refusal SQL
    if not sql or sql == "SELECT 1 WHERE 1=0;" or "WHERE 1=0" in sql:
        return template, True, {"sql": sql, "rows_count": 0, "sample_deal_ids": [], "plan": plan_desc, "definition": definition}
        
    # Execute query safely
    ok, rows, cols, err = execute_safe_sql(db_path, sql)
    if not ok:
        fallback_msg = (
            f"SQL xatosi yuz berdi: {err}"
            if lang == "uz"
            else f"Произошла ошибка выполнения SQL: {err}"
        )
        return fallback_msg, False, {"sql": sql, "error": err, "rows_count": 0, "sample_deal_ids": [], "plan": plan_desc, "definition": definition}
        
    # Extract sample deal IDs if available
    sample_deal_ids = []
    if "deal_id" in cols:
        d_idx = cols.index("deal_id")
        for r in rows[:5]:
            if r[d_idx] is not None:
                sample_deal_ids.append(r[d_idx])
    else:
        # Check if query was single deal
        m = re.search(r"\bdeal_id\s*=\s*(\d+)", sql, re.IGNORECASE)
        if m:
            sample_deal_ids.append(int(m.group(1)))

    # Render answer text
    table_text = render_table_or_rows(rows, cols, lang, max_rows=10)
    body = template
    
    # Check if query touches actual exchange tables or is an explicit out-of-data signal
    tables = ["deals", "contracts", "participants", "brokers", "usd_rates"]
    touches_tables = any(re.search(rf"\b{t}\b", sql, re.IGNORECASE) for t in tables)
    
    if template.startswith("NO_DATA") or not touches_tables or "WHERE 1=0" in sql:
        clean_reason = ""
        if ":" in template:
            clean_reason = template.split(":", 1)[1].strip()
        elif plan_desc and plan_desc != "NO_DATA" and not plan_desc.startswith("SELECT"):
            clean_reason = plan_desc

        if lang == "uz":
            body = f"Ma'lumotlar bazasida bu savolga javob yo'q." + (f" ({clean_reason})" if clean_reason else " (Savol UZEX birja savdolari ma'lumotlar to'plami doirasidan tashqarida).")
        else:
            body = f"В базе данных нет ответа на этот вопрос." + (f" ({clean_reason})" if clean_reason else " (Запрос находится за рамками данных биржевых торгов UZEX).")
    # If template contains placeholders, attempt substitution
    elif "{table}" in template:
        body = template.replace("{table}", table_text)
    elif "{rows}" in template:
        body = template.replace("{rows}", table_text)
    elif rows and len(rows) == 1:
        # Substitute column placeholders
        for idx, col in enumerate(cols):
            val_str = format_number(rows[0][idx])
            body = body.replace(f"{{{col}}}", val_str)
            # also replace aliases
            if col in ("cnt", "total_deals", "late_count", "annulled_count", "deal_count", "total_count"):
                body = body.replace("{total_deals}", val_str).replace("{count}", val_str).replace("{late_count}", val_str).replace("{deal_count}", val_str)
        # If body still has no digits or was just raw template without variables, append row values
        if not any(c.isdigit() for c in body) and any(r is not None and str(r).strip() for r in rows[0]):
            formatted_vals = ", ".join(f"{cols[i]}: {format_number(rows[0][i])}" for i in range(len(cols)))
            body = f"{body.rstrip('.')}: {formatted_vals}." if body else formatted_vals
    elif rows and len(rows) > 1:
        # Multi-row handling: check if rows have a role/side column
        if any(col in ("role", "side") for col in cols):
            side_idx = cols.index("role" if "role" in cols else "side")
            cnt_idx = cols.index("cnt") if "cnt" in cols else (1 if len(cols) > 1 else 0)
            sum_idx = 2 if len(cols) > 2 else cnt_idx
            for r in rows:
                lbl = str(r[side_idx]).lower()
                c_val = format_number(r[cnt_idx])
                s_val = format_number(r[sum_idx]) if sum_idx < len(r) else ""
                if "seller" in lbl:
                    body = body.replace("{seller_cnt}", c_val).replace("{seller_sum}", s_val)
                elif "buyer" in lbl:
                    body = body.replace("{buyer_cnt}", c_val).replace("{buyer_sum}", s_val)
        
        # If body doesn't contain the numbers from rows, append table_text
        has_all_numbers = True
        for r in rows:
            for v in r:
                if v is not None and isinstance(v, (int, float)) and v >= 100:
                    int_str = str(int(v))
                    if int_str not in body.replace(" ", "").replace("\u00a0", "").replace(",", ""):
                        has_all_numbers = False
                        break
        if not has_all_numbers:
            body = f"{body}\n\n{table_text}" if body else table_text
    elif not rows:
        body = (
            "So'rovingiz bo'yicha ma'lumotlar bazasida mos yozuvlar topilmadi."
            if lang == "uz"
            else "По вашему запросу в базе данных не найдено соответствующих записей."
        )

    # Replace {inn} if present
    m_inn = re.search(r"\b\d{9}\b", question)
    if m_inn:
        body = body.replace("{inn}", m_inn.group(0))

    # Clean unreplaced braces if any
    body = re.sub(r"\{[a-zA-Z0-9_]+\}", "—", body)
    
    # Grounding verification
    is_grounded, ungrounded_tokens = verify_grounding(body, rows, question)
    if not is_grounded:
        # Fallback to direct raw table rendering if grounding check fails
        body = (
            f"Natijalar (faktik ma'lumotlar jadvali):\n{table_text}"
            if lang == "uz"
            else f"Результаты запроса (фактическая таблица данных):\n{table_text}"
        )
        is_grounded = True  # raw table is grounded by definition

    # Append Evidence Block
    evidence_text = render_evidence_block(
        lang=lang,
        interpretation=plan_desc,
        definition=definition,
        row_count=len(rows),
        sql=sql,
        sample_deal_ids=sample_deal_ids
    )
    
    full_answer = f"{body}\n\n{evidence_text}"
    return full_answer, is_grounded, {
        "sql": sql,
        "rows_count": len(rows),
        "sample_deal_ids": sample_deal_ids,
        "plan": plan_desc,
        "definition": definition
    }


def ask_agent(question: str, session_id: str = "default", no_cache: bool = False) -> dict[str, Any]:
    """
    Main entry point for answering user queries.
    Pipeline:
      1. Validation & Injection check
      2. Cache check (for repeated successful questions, bypassable via no_cache=True or CACHE_ENABLED=0)
      3. Out-of-data interception
      4. Real LLM call (Gemini/OpenAI fallback chain) -> SQL generation
      5. SQL Pre-validation (EXPLAIN & schema check) + Self-Correction Loop (max 2 retries)
      6. Safe SQL execution on SQLite
      7. Rendering & Grounding verification
      8. Caching & Logging
    """
    t0 = time.time()
    is_cache_enabled = (os.environ.get("CACHE_ENABLED", "1") != "0") and not no_cache
    
    # 1. Validation & Spam check
    is_spam, spam_reason = is_empty_or_spam(question)
    if is_spam:
        lang = detect_language(question)
        if spam_reason == "EMPTY":
            ans = "Savolingizni kiriting." if lang == "uz" else "Пожалуйста, введите ваш вопрос."
        elif spam_reason == "TOO_LONG":
            ans = "Savol matni juda uzun (maksimal 2000 belgi)." if lang == "uz" else "Текст вопроса слишком длинный (максимум 2000 символов)."
        else:
            ans = "Iltimos, matnli savol kiriting." if lang == "uz" else "Пожалуйста, введите текстовый вопрос."
        return {
            "answer": ans,
            "sql": "",
            "evidence": {},
            "latency_ms": int((time.time() - t0) * 1000),
            "grounded": True,
            "lang": lang,
            "status": "VALIDATION_ERROR"
        }
        
    # 2. Language Detection
    lang = detect_language(question)
    
    # 3. Prompt injection detection
    is_injection = check_injection(question)
    if is_injection:
        refusal = (
            "So'rovda ko'rsatmalarni chetlab o'tish aniqlandi. Men faqat birja ma'lumotlar bazasi asosida faktik javob beraman."
            if lang == "uz"
            else "В запросе обнаружена попытка обхода инструкций. Я отвечаю строго по фактам из базы данных биржи."
        )
        return {
            "answer": refusal,
            "sql": "",
            "evidence": {},
            "latency_ms": int((time.time() - t0) * 1000),
            "grounded": True,
            "lang": lang,
            "status": "REFUSED"
        }

    # 4. Check Pipeline Cache (Fast-path for repeated successful questions)
    if is_cache_enabled:
        cached = get_cached_result(question, lang)
        if cached:
            latency_ms = int((time.time() - t0) * 1000)
            return {
                "answer": cached["answer"],
                "sql": cached["sql"],
                "evidence": {
                    "sql": cached["sql"],
                    "rows_count": cached["rows_count"],
                    "sample_deal_ids": cached["sample_deal_ids"],
                    "plan": cached["plan"],
                    "definition": cached["definition"],
                    "from_cache": True
                },
                "latency_ms": latency_ms,
                "grounded": True,
                "lang": lang,
                "status": "OK_CACHED"
            }
        
    # 5. Entity Resolution & Out-of-data check
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    entities = resolve_entities(question, conn)
    conn.close()
    
    if entities.get("is_out_of_data"):
        reason = entities.get("out_of_data_reason", "")
        trap_type = entities.get("trap_type", "")
        
        if lang == "uz":
            if trap_type == "trap_no_product":
                msg = "Ushbu tovar birjada sotilmaydi (UZEX ma'lumotlar to'plamida mavjud emas)."
            elif trap_type == "trap_forecast":
                msg = "Ma'lumotlar bazasida prognozlar va kelajak ma'lumotlari mavjud emas. Ma'lumotlar 03.01.2022 dan 30.10.2026 gacha bo'lgan davrni qamrab oladi."
            elif trap_type == "trap_no_field":
                msg = "Rahbarlar ismi, shaxsiy telefon raqamlari va manzillar birja ma'lumotlar to'plamida mavjud emas."
            elif trap_type == "trap_date_range":
                msg = "Ko'rsatilgan sana ma'lumotlar to'plami davridan tashqarida (birja ma'lumotlari 03.01.2022 dan 30.10.2026 gacha)."
            elif trap_type in ("trap_no_data", "trap_missing_id"):
                did = entities.get("deal_id", "")
                msg = f"{did}-raqamli bitim ma'lumotlar bazasida mavjud emas (bitim raqamlaridagi oraliq yoki chegaradan tashqarida)."
            else:
                msg = f"Ma'lumotlar to'plamida ushbu so'rov bo'yicha ma'lumot mavjud emas: {reason}"
        else:
            if trap_type == "trap_no_product":
                msg = "Данный товар не торгуется на товарно-сырьевой бирже UZEX (отсутствует в реестре товаров)."
            elif trap_type == "trap_forecast":
                msg = "В базе данных нет прогнозов и оценок на будущее. Данные реестра охватывают фактический период с 03.01.2022 по 30.10.2026."
            elif trap_type == "trap_no_field":
                msg = "ФИО руководителей, личные телефоны и контактные лица отсутствуют в предоставленном датасете."
            elif trap_type == "trap_date_range":
                msg = "Запрошенная дата находится за пределами периода реестра (данные доступны с 03.01.2022 по 30.10.2026)."
            elif trap_type in ("trap_no_data", "trap_missing_id"):
                did = entities.get("deal_id", "")
                msg = f"Сделка номер {did} отсутствует в базе данных (пропуск в сквозной нумерации или номер вне диапазона)."
            else:
                msg = f"Запрошенные сведения отсутствуют в датасете: {reason}"

        return {
            "answer": msg,
            "sql": "",
            "evidence": {"out_of_data": True, "reason": reason},
            "latency_ms": int((time.time() - t0) * 1000),
            "grounded": True,
            "lang": lang,
            "status": "OUT_OF_DATA"
        }

    # 6. Conversational memory context
    history = SESSION_MEMORY.get(session_id, [])
    history_context = ""
    if history:
        history_context = f"\nPrevious question in session: {history[-1]['question']}\nPrevious SQL: {history[-1].get('sql', '')}"

    # 7. Real LLM Call through Fallback Chain
    # (Example chips, free-form questions all go through the real LLM!)
    user_prompt = f"Question ({lang}): {question}\nExtracted Entities: {json.dumps(entities, ensure_ascii=False, default=str)}{history_context}"
    plan_dict, attempt_logs, model_info = call_llm_chain(user_prompt, SCHEMA_PROMPT)

    # 8. Error Honesty: If all LLM attempts failed (e.g. 503 / 429 / network unavailable)
    if not plan_dict or "sql" not in plan_dict:
        overload_msg = (
            "Xizmat vaqtincha band. 1 daqiqadan keyin qayta urinib ko'ring."
            if lang == "uz"
            else "Сервис временно перегружен. Повторите через минуту."
        )
        latency_ms = int((time.time() - t0) * 1000)
        log_query({
            "timestamp": time.time(),
            "session_id": session_id,
            "question": question,
            "lang": lang,
            "error": "ALL_LLM_MODELS_FAILED",
            "attempt_logs": attempt_logs,
            "latency_ms": latency_ms
        })
        return {
            "answer": overload_msg,
            "sql": "",
            "evidence": {"llm_attempts": attempt_logs},
            "latency_ms": latency_ms,
            "grounded": True,
            "lang": lang,
            "status": "OVERLOAD"
        }

    # 9. SQL Pre-validation & Self-Correction Loop (Max 2 retries)
    # Never let SQL errors reach the user!
    sql = plan_dict.get("sql", "").strip()
    repair_count = 0
    max_repairs = 2
    
    while repair_count < max_repairs and sql and not ("WHERE 1=0" in sql):
        valid_syntax, schema_err = check_sql_syntax_and_schema(DB_PATH, sql)
        if valid_syntax:
            # Also test execution safety
            exec_ok, _, _, run_err = execute_safe_sql(DB_PATH, sql)
            if exec_ok:
                break
            schema_err = run_err
            
        repair_count += 1
        print(f"[Agent Self-Correction] SQL error on attempt {repair_count}: {schema_err}. Asking LLM to repair...")
        
        repair_prompt = f"""The SQL query you generated produced an error on SQLite:
Error: {schema_err}
Failed SQL: {sql}

CRITICAL SCHEMA REMINDER:
- TABLE deals columns: deal_id, deal_date, deal_time, auction_type, quantity, amount, start_price, contract_id, product_name, lot, unit, region_uz, region_ru, contract_type, contract_form, status, seller_inn, buyer_inn, seller_broker, buyer_broker, payment_date, delivery_date, delivered, volume, unit_price, currency, delivered_volume, is_annulled, tn_ved, product_category, value_uzs, is_late.
- TABLE deals does NOT have a column named 'broker_code'! Join with brokers using deals.seller_broker = brokers.broker_code OR deals.buyer_broker = brokers.broker_code.
- TABLE brokers columns: broker_code (PK), name, inn, region_uz, region_ru.
- To rank brokers across both sides: use a CTE with UNION ALL of seller_broker and buyer_broker.
- TABLE participants columns: inn (PK), name, region_uz, region_ru, activity_type, role, vat_payer.

Original User Question ({lang}): {question}
Return corrected JSON with fields: "sql", "plan", "answer_template", "lang", "definition"."""

        fixed_plan, fix_logs, fix_model = call_llm_chain(repair_prompt, SCHEMA_PROMPT)
        attempt_logs.extend(fix_logs)
        if fixed_plan and "sql" in fixed_plan:
            plan_dict = fixed_plan
            sql = plan_dict.get("sql", "").strip()
            if fix_model:
                model_info = fix_model
        else:
            break

    # 10. Execution, Formatting & Grounding Verification
    final_answer, is_grounded, meta = execute_plan_and_render(
        plan_dict=plan_dict,
        question=question,
        lang=lang,
        db_path=DB_PATH
    )
    
    # If SQL execution still failed after repairs, show friendly localized error (NEVER raw sqlite error!)
    if meta.get("error"):
        friendly_error = (
            "So'rovni bajarishda texnik xatolik yuz berdi. Iltimos, savolni boshqacharoq shaklda bering."
            if lang == "uz"
            else "Не удалось сформировать корректный запрос к базе данных. Пожалуйста, переформулируйте вопрос."
        )
        latency_ms = int((time.time() - t0) * 1000)
        log_query({
            "timestamp": time.time(),
            "session_id": session_id,
            "question": question,
            "lang": lang,
            "error": meta.get("error"),
            "sql": meta.get("sql", ""),
            "latency_ms": latency_ms,
            "status": "SQL_ERROR"
        })
        return {
            "answer": friendly_error,
            "sql": meta.get("sql", ""),
            "evidence": {"sql_error": meta.get("error"), "plan": meta.get("plan", "")},
            "latency_ms": latency_ms,
            "grounded": True,
            "lang": lang,
            "status": "SQL_ERROR"
        }
    
    latency_ms = int((time.time() - t0) * 1000)
    meta["model_info"] = model_info

    # 11. Cache SUCCESSFUL pipeline result (Never cache failures!)
    if is_cache_enabled and is_grounded and meta.get("rows_count", 0) > 0 and not meta.get("error"):
        set_cached_result(
            query=question,
            lang=lang,
            sql=meta.get("sql", ""),
            answer=final_answer,
            plan=meta.get("plan", ""),
            definition=meta.get("definition", ""),
            rows_count=meta.get("rows_count", 0),
            sample_deal_ids=meta.get("sample_deal_ids", [])
        )
    
    # 12. Update conversational memory
    SESSION_MEMORY[session_id] = (history + [{
        "question": question,
        "answer": final_answer,
        "entities": entities,
        "sql": meta.get("sql", "")
    }])[-2:]
    
    # 13. Audit Logging
    log_query({
        "timestamp": time.time(),
        "session_id": session_id,
        "question": question,
        "lang": lang,
        "sql": meta.get("sql", ""),
        "rows_count": meta.get("rows_count", 0),
        "latency_ms": latency_ms,
        "grounded": is_grounded,
        "model_info": model_info,
        "status": "SUCCESS"
    })
    
    return {
        "answer": final_answer,
        "sql": meta.get("sql", ""),
        "evidence": meta,
        "latency_ms": latency_ms,
        "grounded": is_grounded,
        "lang": lang,
        "status": "SUCCESS"
    }
