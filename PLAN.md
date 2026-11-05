# Execution Plan & Technical Specification

## 1. Architecture & Component Specification

### File-by-File Specification

#### `app/dictionaries.py`
- **Purpose**: Canonical ground truth dictionary for all 40 TN VED codes, regional transliterations, sort/grade normalization, status translations, units, and currencies.
- **Key Objects**:
  - `TN_VED_PRODUCTS`: Dict mapping 6-digit TN VED code -> `{"canon_ru": str, "canon_uz_lat": str, "canon_uz_cyr": str, "synonyms": list[str], "unit": str, "category": str, "industry": str, "group": str}`.
  - `REGION_UZ_TO_RU`, `REGION_RU_TO_UZ`, `REGION_ALIASES`: Exact bidirectional mapping between 14 regions in Uzbek Latin and Russian.
  - `STATUS_RU`, `STATUS_UZ`: 8 deal lifecycle statuses with exact definitions.
  - `UNIT_RU`, `UNIT_UZ`, `CURRENCY_RU`, `CURRENCY_UZ`: Exact unit and currency text representations.
  - `SORT_NORM`, `CLASS_NORM`, `TYPE_NORM`: Grade normalization maps.

#### `app/lang_detect.py`
- **Purpose**: Detect user question language (Uzbek vs Russian) and guard against prompt injections or empty queries.
- **Functions**:
  - `detect_language(text: str) -> str`: Returns `"uz"` or `"ru"`. Uzbek detected via specific characters (`o'`, `g'`, `sh`, `ch`, `o‘`, `g‘`, `q`, `x`) and lexicon (`qancha`, `nechta`, `bitim`, `yil`, `narxi`, etc.). Defaults to `"ru"` if Cyrillic Russian.
  - `check_injection(text: str) -> bool`: Detects jailbreak phrases ("ignore rules", "invent", "забудь инструкции", etc.).

#### `app/entity_resolver.py`
- **Purpose**: Deterministic entity extraction before SQL/LLM call.
- **Functions**:
  - `resolve_entities(query: str, db_conn) -> dict`:
    - `deal_id`: Optional[int] (matches 100001..604956)
    - `inn`: Optional[str] (exact 9 digits)
    - `broker_code`: Optional[str] (BK001..BK120)
    - `tn_ved`: Optional[str] (matches products or synonyms)
    - `region_uz`: Optional[str] (matches canonical region)
    - `year`: Optional[int] (2022..2026)
    - `date_iso`: Optional[str] ('YYYY-MM-DD')
    - `company_candidates`: list[dict] (matched companies via Latin transliteration & RapidFuzz)
    - `is_out_of_data`: bool (gold, directors, phone numbers, forecasts, dates outside 2022-2026)

#### `app/sql_guard.py`
- **Purpose**: Absolute security and read-only enforcement on generated SQL.
- **Functions**:
  - `validate_sql(sql: str) -> tuple[bool, str]`:
    - Checks SQL begins with `SELECT` or `WITH ... SELECT`.
    - Disallows forbidden keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `ATTACH`, `DETACH`, `PRAGMA`, `VACUUM`, `EXEC`, `CREATE`).
    - Ensures maximum `LIMIT 1000`.
  - `execute_safe_sql(db_conn, sql: str, timeout_sec: float = 20.0) -> list[tuple]`:
    - Executes in read-only transaction with timeout interrupt.

#### `app/verifier.py`
- **Purpose**: Grounding verifier ensuring zero hallucination.
- **Functions**:
  - `verify_grounding(answer_text: str, rows: list[tuple], allowed_tokens: set[str]) -> tuple[bool, list[str]]`:
    - Extracts all numerical tokens, dates, and entity identifiers from `answer_text`.
    - Verifies that every extracted number/date/ID is present in `rows` or in system metadata (e.g., date ranges).
    - If ungrounded numbers are found, returns `(False, reasons)` triggering re-generation or fallback.

#### `app/renderer.py`
- **Purpose**: Render clear, natural, factual answers from SQL rows with required Evidence block.
- **Functions**:
  - `render_answer(lang: str, template: str, rows: list[tuple], columns: list[str], plan: str, sql: str, definition: str, sample_deal_ids: list[int]) -> str`:
    - Formats numbers with thousand separators.
    - Uses exact Uzbek or Russian grammatical units and currency words.
    - Appends mandatory `### Asos / Обоснование (Evidence)` block containing:
      - Interpretation & filters
      - Definition used (e.g. "excluding annulled deals")
      - Number of rows
      - Executed SQL
      - Sample deal IDs (up to 5)

#### `app/llm.py`
- **Purpose**: Provider-agnostic LLM fallback chain.
- **Functions**:
  - `call_llm(prompt: str, system_prompt: str, json_mode: bool = True) -> dict`:
    - Chain: Google GenAI (`gemini-2.5-flash` or `gemini-1.5-flash`) -> OpenAI-compatible -> Anthropic.
    - Fallback: Deterministic query planner when offline or API key absent.

#### `app/agent.py`
- **Purpose**: Master orchestrator executing the 8-step pipeline with retry logic and conversational follow-up memory.
- **Functions**:
  - `ask_agent(question: str, session_id: str = "default") -> dict`:
    - Returns `{"answer": str, "sql": str, "evidence": dict, "latency_ms": int, "grounded": bool}`.

#### `app/server.py`
- **Purpose**: High-performance FastAPI server.
- **Endpoints**:
  - `GET /`: Serves static web interface.
  - `POST /api/ask`: Body `{"question": str, "session_id": str}` -> JSON response.
  - `GET /api/health`: Health status, DB stats, memory usage.

---

## 2. Fifteen Core Question Types & Exact SQL Patterns

| # | Question Type | Language | Typical Question | Exact SQL Pattern |
|---|---|---|---|---|
| 1 | Single Deal Lookup | RU/UZ | "Покажи сделку номер 247890" | `SELECT * FROM deals WHERE deal_id = 247890 LIMIT 1;` |
| 2 | Contract Lookup | RU/UZ | "Контракт 101166 ҳақида маълумот" | `SELECT * FROM contracts WHERE contract_id = '101166' LIMIT 1;` |
| 3 | Company by INN | RU/UZ | "ИНН 921912462 бўлган компания" | `SELECT * FROM participants WHERE inn = '921912462' LIMIT 1;` |
| 4 | Product Volume by Year | RU/UZ | "2023 yilda qancha paxta sotilgan?" | `SELECT d.unit, SUM(d.volume) AS vol, COUNT(*) AS cnt, ROUND(SUM(d.value_uzs), 2) AS val FROM deals d WHERE d.tn_ved = '520100' AND d.deal_date BETWEEN '2023-01-01' AND '2023-12-31' AND d.is_annulled = 0 GROUP BY d.unit;` |
| 5 | Average Unit Price | RU/UZ | "2024 yilda sementning o'rtacha narxi" | `SELECT d.unit, d.currency, ROUND(AVG(d.unit_price), 2) AS avg_p, COUNT(*) AS cnt FROM deals d WHERE d.tn_ved = '252329' AND d.deal_date BETWEEN '2024-01-01' AND '2024-12-31' AND d.is_annulled = 0 GROUP BY d.unit, d.currency;` |
| 6 | Top Sellers | RU/UZ | "Топ-5 продавцов пшеницы" | `SELECT d.seller_inn, p.name, SUM(d.volume) AS vol, COUNT(*) AS cnt FROM deals d JOIN participants p ON d.seller_inn = p.inn WHERE d.tn_ved = '100199' AND d.is_annulled = 0 GROUP BY d.seller_inn ORDER BY vol DESC LIMIT 5;` |
| 7 | Top Buyers | RU/UZ | "Eng yirik xaridorlar kimlar?" | `SELECT d.buyer_inn, p.name, COUNT(*) AS cnt, ROUND(SUM(d.value_uzs), 2) AS total FROM deals d JOIN participants p ON d.buyer_inn = p.inn WHERE d.is_annulled = 0 GROUP BY d.buyer_inn ORDER BY total DESC LIMIT 5;` |
| 8 | Export Deals & USD Sum | RU/UZ | "Сколько экспортных сделок и их сумма?" | `SELECT COUNT(*) AS cnt, ROUND(SUM(amount), 2) AS usd, ROUND(SUM(value_uzs), 2) AS uzs FROM deals WHERE contract_type = 'Экспортный' AND is_annulled = 0;` |
| 9 | USD Exchange Rate | RU/UZ | "2024 yil 15 iyun kuni dollar kursi" | `SELECT date, rate FROM usd_rates WHERE date = '2024-06-15' LIMIT 1;` |
| 10 | Status Distribution | RU/UZ | "Сделки по статусам" | `SELECT status, COUNT(*) AS cnt FROM deals GROUP BY status ORDER BY cnt DESC;` |
| 11 | Late Delivery Analysis | RU/UZ | "Сколько просроченных поставок в Ташкенте?" | `SELECT COUNT(*) AS late_cnt, ROUND(SUM(value_uzs), 2) AS val FROM deals WHERE is_late = 1 AND region_uz = 'Toshkent shahri';` |
| 12 | Region Analysis | RU/UZ | "Qaysi viloyatda eng ko'p bitim tuzilgan?" | `SELECT region_uz, region_ru, COUNT(*) AS cnt, ROUND(SUM(value_uzs), 2) AS val FROM deals WHERE is_annulled = 0 GROUP BY region_uz ORDER BY cnt DESC LIMIT 5;` |
| 13 | Broker Activity | RU/UZ | "Сколько сделок у брокера BK060?" | `SELECT 'seller' AS side, COUNT(*) AS cnt FROM deals WHERE seller_broker = 'BK060' AND is_annulled = 0 UNION ALL SELECT 'buyer', COUNT(*) FROM deals WHERE buyer_broker = 'BK060' AND is_annulled = 0;` |
| 14 | Ambiguous Company Name | RU/UZ | "Информация о компании Gehu Kimyo" | `SELECT inn, name, region_uz, role FROM participants WHERE name_key_latin LIKE '%gehukimyo%' LIMIT 10;` |
| 15 | Out-of-Data / Non-existent | RU/UZ | "999999-raqamli bitim / Oltin narxi" | `[Pre-LLM Guard detects missing deal ID / unlisted commodity -> NO_DATA response]` |

---

## 3. Implementation Checklist (MVP First)

- [x] **Item 1: Database build & verification** (CRITICAL FOR 60 PTS)
  - 500,000 deals, 6,616 contracts, 14,392 participants, 120 brokers, 1,765 exchange rates.
  - Derived columns: volume, unit_price, value_uzs, is_late, is_annulled, delivered_volume.
  - Passed sanity checks: deal 247890 exists, 999999 returns none, 17,805 late deliveries.

- [x] **Item 2: Core Pipeline & CLI (`cli.py`)** (CRITICAL FOR 60 PTS)
  - Implemented `app/lang_detect.py`, `app/entity_resolver.py`, `app/sql_guard.py`, `app/verifier.py`, `app/renderer.py`, `app/agent.py`.
  - CLI interactive & batch query mode answering 15 question types in RU & UZ.

- [x] **Item 3: Web Service + Frontend** (CRITICAL FOR 20 PTS)
  - FastAPI server (`app/server.py`) with `/api/ask`, `/api/health`, `/`.
  - Single-file mobile-friendly frontend (`static/index.html`) with RU/UZ toggle, example chips, collapsible evidence block, copy button.

- [x] **Item 4: SQL Guard + Grounding Verifier + Error Retry** (CRITICAL FOR 60 PTS)
  - Strict SELECT-only, 20s timeout, limits.
  - Grounding verifier verifies numbers against DB rows.
  - Automatic error-feedback retry (up to 2 attempts).

- [x] **Item 5: Balanced Golden Set & Verification Script (`scripts/golden_check.py`)** (CRITICAL FOR 60 PTS)
  - 50 questions: 25 UZ, 25 RU, 12 traps.
  - Independent pandas/SQL ground truth.
  - Automated evaluation script outputting 100.0% pass rate and 203ms average latency.

- [x] **Item 6: Offline Unit Tests (`tests/test_offline.py`)** (CRITICAL FOR 20 PTS)
  - 100% offline unit tests without external API dependencies.
  - 10 passed in 0.11s testing normalization, transliteration, entity resolution, SQL safety, grounding verification, and full TN VED dictionary coverage.

- [x] **Item 7: Deployment Configuration** (CRITICAL FOR 24/7 PROTOTYPE)
  - `Dockerfile`, `docker-compose.yml`, `.env.example`, `requirements.txt`.
  - Always-on hosting documentation, health check, restart policies.

- [x] **Item 8: Documentation & Submission** (CRITICAL FOR 20 PTS)
  - `docs/SOLUTION.md` in Uzbek and Russian.
  - `FORM_ANSWERS.txt` with ready-to-paste text.
