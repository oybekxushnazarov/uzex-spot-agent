# -*- coding: utf-8 -*-
"""
build_db.py — Build the normalized SQLite database from UZEX spot data CSVs.

Usage:
    python -X utf8 scripts/build_db.py [--data-dir DATA_DIR] [--db-path DB_PATH]

Defaults:
    DATA_DIR = data/raw/uzex_spot_data/uzex_spot_data
    DB_PATH  = data/uzex.db
"""

import argparse
import csv
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta

# ────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────

def parse_money(s: str) -> float | None:
    """'304 547 938.4' -> 304547938.4"""
    if not s or s.strip() == "":
        return None
    return float(s.replace(" ", "").replace("\u00a0", ""))


def parse_date_ddmmyyyy(s: str) -> str | None:
    """'03.01.2022' -> '2022-01-03' (ISO)."""
    if not s or s.strip() == "":
        return None
    parts = s.strip().split(".")
    if len(parts) != 3:
        return None
    return f"{parts[2]}-{parts[1]}-{parts[0]}"


def parse_int(s: str) -> int | None:
    if not s or s.strip() == "":
        return None
    return int(s.replace(" ", "").replace("\u00a0", ""))


def parse_float(s: str) -> float | None:
    if not s or s.strip() == "":
        return None
    return float(s.replace(" ", "").replace("\u00a0", ""))


# ────────────────────────────────────────────────────────────────
# Region mapping (UZ Latin in deals ↔ Russian in contracts)
# ────────────────────────────────────────────────────────────────

REGION_UZ_TO_RU = {
    "Toshkent shahri": "г. Ташкент",
    "Toshkent viloyati": "Ташкентская область",
    "Samarqand viloyati": "Самаркандская область",
    "Namangan viloyati": "Наманганская область",
    "Andijon viloyati": "Андижанская область",
    "Farg'ona viloyati": "Ферганская область",
    "Buxoro viloyati": "Бухарская область",
    "Qashqadaryo viloyati": "Кашкадарьинская область",
    "Surxondaryo viloyati": "Сурхандарьинская область",
    "Xorazm viloyati": "Хорезмская область",
    "Navoiy viloyati": "Навоийская область",
    "Jizzax viloyati": "Джизакская область",
    "Sirdaryo viloyati": "Сырдарьинская область",
    "Qoraqalpog'iston Respublikasi": "Республика Каракалпакстан",
}

REGION_RU_TO_UZ = {v: k for k, v in REGION_UZ_TO_RU.items()}


# ────────────────────────────────────────────────────────────────
# Grade / class / sort normalization
# ────────────────────────────────────────────────────────────────

def normalize_sort(s: str | None) -> str | None:
    """Normalize Сорт товара to canonical form."""
    if not s:
        return None
    s = s.strip().lower()
    # Map to canonical
    if s in ("высший сорт", "высшего сорта"):
        return "высший сорт"
    if s in ("1 сорт", "1-сорта", "первый сорт", "i сорт"):
        return "1 сорт"
    if s in ("2 сорт", "2-сорта", "ii сорт", "второй сорт"):
        return "2 сорт"
    if s in ("3 сорт", "3-сорта", "iii сорт", "третий сорт"):
        return "3 сорт"
    return s  # return as-is if unknown


def normalize_class(s: str | None) -> str | None:
    """Normalize Класс товара to canonical form."""
    if not s:
        return None
    s = s.strip().lower()
    if s in ("1 класс", "1-класс", "i класс"):
        return "1 класс"
    if s in ("2 класс", "2-класс", "ii класс"):
        return "2 класс"
    if s in ("3 класс", "3-класс", "iii класс"):
        return "3 класс"
    if s in ("4 класс", "4-класс", "iv класс"):
        return "4 класс"
    if s == "а500с":
        return "А500С"
    return s


def normalize_type(s: str | None) -> str | None:
    """Normalize Тип товара to canonical lowercase."""
    if not s:
        return None
    return s.strip().lower()


# ────────────────────────────────────────────────────────────────
# Company name → Latin key for fuzzy matching
# ────────────────────────────────────────────────────────────────

_CYR_TO_LAT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l',
    'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's',
    'т': 't', 'у': 'u', 'ф': 'f', 'х': 'x', 'ц': 'ts', 'ч': 'ch',
    'ш': 'sh', 'щ': 'sh', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e',
    'ю': 'yu', 'я': 'ya', 'ё': 'yo',
    'қ': 'q', 'ғ': 'g', 'ҳ': 'h', 'ў': 'o',
}

def company_key_latin(name: str) -> str:
    """Transliterate company name to a comparable Latin key (lowercase, no punctuation)."""
    s = name.lower()
    result = []
    for ch in s:
        if ch in _CYR_TO_LAT_MAP:
            result.append(_CYR_TO_LAT_MAP[ch])
        else:
            result.append(ch)
    s = "".join(result)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


# ────────────────────────────────────────────────────────────────
# Schema
# ────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS brokers (
    broker_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    inn TEXT NOT NULL,
    region_uz TEXT NOT NULL,
    region_ru TEXT
);

CREATE TABLE IF NOT EXISTS participants (
    inn TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    region_uz TEXT NOT NULL,
    region_ru TEXT,
    activity_type TEXT NOT NULL,
    role TEXT NOT NULL,          -- Продавец / Покупатель
    vat_payer TEXT NOT NULL,     -- Да / Нет
    name_key_latin TEXT         -- lowercased transliterated key
);

CREATE TABLE IF NOT EXISTS usd_rates (
    date TEXT PRIMARY KEY,       -- ISO YYYY-MM-DD
    rate REAL NOT NULL           -- UZS per 1 USD
);

CREATE TABLE IF NOT EXISTS contracts (
    contract_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    brand TEXT,
    size TEXT,
    sort TEXT,                   -- original
    sort_norm TEXT,              -- normalized
    type TEXT,                   -- original
    type_norm TEXT,              -- normalized
    class TEXT,                  -- original
    class_norm TEXT,             -- normalized
    tn_ved TEXT NOT NULL,        -- Код ТН ВЭД
    product_group TEXT NOT NULL,
    product_category TEXT NOT NULL,
    industry TEXT NOT NULL,
    unit TEXT NOT NULL,
    lot INTEGER NOT NULL,
    currency TEXT NOT NULL,      -- 'UZS' or 'USD'
    base_price REAL NOT NULL,
    deposit_pct TEXT NOT NULL,
    delivery_basis TEXT NOT NULL,
    region_ru TEXT NOT NULL,
    region_uz TEXT,
    warehouse_address TEXT NOT NULL,
    auction_type TEXT NOT NULL,
    contract_type TEXT NOT NULL,  -- Внутренний / Экспортный
    contract_form TEXT NOT NULL,  -- Спот / Форвард / Фьючерс
    payment_days INTEGER NOT NULL,
    delivery_days INTEGER NOT NULL,
    packaging TEXT NOT NULL,
    seller_inn TEXT NOT NULL,
    reg_date TEXT NOT NULL,       -- ISO
    valid_until TEXT NOT NULL     -- ISO
);

CREATE TABLE IF NOT EXISTS deals (
    deal_id INTEGER PRIMARY KEY,
    deal_date TEXT NOT NULL,      -- ISO
    deal_time TEXT NOT NULL,
    auction_type TEXT NOT NULL,
    quantity INTEGER NOT NULL,    -- number of lots
    amount REAL NOT NULL,         -- in contract currency
    start_price REAL NOT NULL,    -- per unit, in contract currency
    contract_id TEXT NOT NULL,
    product_name TEXT NOT NULL,   -- as in registry
    lot INTEGER NOT NULL,
    unit TEXT NOT NULL,
    region_uz TEXT NOT NULL,
    region_ru TEXT,
    contract_type TEXT NOT NULL,  -- Внутренний / Экспортный
    contract_form TEXT NOT NULL,
    status TEXT NOT NULL,
    seller_inn TEXT NOT NULL,
    buyer_inn TEXT NOT NULL,
    seller_broker TEXT NOT NULL,
    buyer_broker TEXT NOT NULL,
    payment_date TEXT,            -- ISO or NULL
    delivery_date TEXT,           -- ISO or NULL
    delivered INTEGER,            -- lots delivered or NULL
    -- derived columns
    volume REAL NOT NULL,         -- quantity * lot (in units)
    unit_price REAL,              -- amount / volume
    currency TEXT NOT NULL,       -- from contract: 'UZS' or 'USD'
    delivered_volume REAL,        -- delivered * lot
    is_annulled INTEGER NOT NULL DEFAULT 0,
    tn_ved TEXT,                  -- from contract
    product_category TEXT,        -- from contract
    FOREIGN KEY (contract_id) REFERENCES contracts(contract_id),
    FOREIGN KEY (seller_inn) REFERENCES participants(inn),
    FOREIGN KEY (buyer_inn) REFERENCES participants(inn),
    FOREIGN KEY (seller_broker) REFERENCES brokers(broker_code),
    FOREIGN KEY (buyer_broker) REFERENCES brokers(broker_code)
);

-- We add is_late and value_uzs after loading usd_rates
-- because we need to look up rates
"""

INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_deals_date ON deals(deal_date);
CREATE INDEX IF NOT EXISTS idx_deals_seller ON deals(seller_inn);
CREATE INDEX IF NOT EXISTS idx_deals_buyer ON deals(buyer_inn);
CREATE INDEX IF NOT EXISTS idx_deals_contract ON deals(contract_id);
CREATE INDEX IF NOT EXISTS idx_deals_status ON deals(status);
CREATE INDEX IF NOT EXISTS idx_deals_region_uz ON deals(region_uz);
CREATE INDEX IF NOT EXISTS idx_deals_region_ru ON deals(region_ru);
CREATE INDEX IF NOT EXISTS idx_deals_tn_ved ON deals(tn_ved);
CREATE INDEX IF NOT EXISTS idx_deals_product_category ON deals(product_category);
CREATE INDEX IF NOT EXISTS idx_deals_seller_broker ON deals(seller_broker);
CREATE INDEX IF NOT EXISTS idx_deals_buyer_broker ON deals(buyer_broker);
CREATE INDEX IF NOT EXISTS idx_deals_currency ON deals(currency);
CREATE INDEX IF NOT EXISTS idx_deals_contract_type ON deals(contract_type);
CREATE INDEX IF NOT EXISTS idx_deals_contract_form ON deals(contract_form);
CREATE INDEX IF NOT EXISTS idx_deals_auction_type ON deals(auction_type);
CREATE INDEX IF NOT EXISTS idx_contracts_seller ON contracts(seller_inn);
CREATE INDEX IF NOT EXISTS idx_contracts_tn_ved ON contracts(tn_ved);
CREATE INDEX IF NOT EXISTS idx_contracts_category ON contracts(product_category);
CREATE INDEX IF NOT EXISTS idx_participants_role ON participants(role);
CREATE INDEX IF NOT EXISTS idx_participants_region ON participants(region_uz);
CREATE INDEX IF NOT EXISTS idx_usd_rates_date ON usd_rates(date);
"""


# ────────────────────────────────────────────────────────────────
# Loaders
# ────────────────────────────────────────────────────────────────

def load_brokers(cur, data_dir):
    path = os.path.join(data_dir, "brokers.csv")
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            region_uz = r["Регион"].strip()
            rows.append((
                r["Код брокера"].strip(),
                r["Наименование"].strip(),
                r["ИНН"].strip(),
                region_uz,
                REGION_UZ_TO_RU.get(region_uz),
            ))
    cur.executemany(
        "INSERT INTO brokers (broker_code, name, inn, region_uz, region_ru) VALUES (?,?,?,?,?)",
        rows,
    )
    print(f"  brokers: {len(rows)} rows")


def load_participants(cur, data_dir):
    path = os.path.join(data_dir, "participants.csv")
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            region_uz = r["Регион"].strip()
            name = r["Наименование"].strip()
            rows.append((
                r["ИНН"].strip(),
                name,
                region_uz,
                REGION_UZ_TO_RU.get(region_uz),
                r["Вид деятельности"].strip(),
                r["Роль"].strip(),
                r["Плательщик НДС"].strip(),
                company_key_latin(name),
            ))
    cur.executemany(
        "INSERT INTO participants (inn, name, region_uz, region_ru, activity_type, role, vat_payer, name_key_latin) VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    print(f"  participants: {len(rows)} rows")


def load_usd_rates(cur, data_dir):
    path = os.path.join(data_dir, "usd_rates.csv")
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            rows.append((
                parse_date_ddmmyyyy(r["Дата"]),
                parse_float(r["Курс"]),
            ))
    cur.executemany(
        "INSERT INTO usd_rates (date, rate) VALUES (?,?)",
        rows,
    )
    print(f"  usd_rates: {len(rows)} rows")


def load_contracts(cur, data_dir):
    path = os.path.join(data_dir, "contracts.csv")
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            region_ru = r["Регион"].strip()
            currency_raw = r["Валюта"].strip()
            currency = "UZS" if "сум" in currency_raw.lower() else "USD"
            rows.append((
                r["Номер контракта"].strip(),
                r["Наименование продукта"].strip(),
                r.get("Марка товара", "").strip() or None,
                r.get("Размер товара", "").strip() or None,
                r.get("Сорт товара", "").strip() or None,
                normalize_sort(r.get("Сорт товара", "").strip() or None),
                r.get("Тип товара", "").strip() or None,
                normalize_type(r.get("Тип товара", "").strip() or None),
                r.get("Класс товара", "").strip() or None,
                normalize_class(r.get("Класс товара", "").strip() or None),
                r["Код ТН ВЭД"].strip(),
                r["Группа товара"].strip(),
                r["Категория товара"].strip(),
                r["Отрасль промышленности"].strip(),
                r["Единица измерения"].strip(),
                parse_int(r["Лот"]),
                currency,
                parse_money(r["Базисная цена"]),
                r["Сумма залога"].strip(),
                r["Базис поставки"].strip(),
                region_ru,
                REGION_RU_TO_UZ.get(region_ru),
                r["Адрес склада"].strip(),
                r["Тип торгов"].strip(),
                r["Тип контракта"].strip(),
                r["Форма контракта"].strip(),
                parse_int(r["Срок оплаты"]),
                parse_int(r["Срок поставки"]),
                r["Упаковка"].strip(),
                r["ИНН продавца"].strip(),
                parse_date_ddmmyyyy(r["Дата регистрации"]),
                parse_date_ddmmyyyy(r["Действует до"]),
            ))
    cur.executemany(
        """INSERT INTO contracts (
            contract_id, product_name, brand, size, sort, sort_norm,
            type, type_norm, class, class_norm,
            tn_ved, product_group, product_category, industry,
            unit, lot, currency, base_price, deposit_pct, delivery_basis,
            region_ru, region_uz, warehouse_address,
            auction_type, contract_type, contract_form,
            payment_days, delivery_days, packaging,
            seller_inn, reg_date, valid_until
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    print(f"  contracts: {len(rows)} rows")


def load_deals(cur, data_dir):
    """Load all deals_YYYY.csv files."""
    # First build contract lookup for currency, tn_ved, product_category
    cur.execute("SELECT contract_id, currency, tn_ved, product_category FROM contracts")
    contract_info = {}
    for cid, cur_val, tn, cat in cur.fetchall():
        contract_info[cid] = (cur_val, tn, cat)

    total = 0
    for year in [2022, 2023, 2024, 2025, 2026]:
        fname = f"deals_{year}.csv"
        path = os.path.join(data_dir, fname)
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = []
            for r in reader:
                region_uz = r["Регион"].strip()
                contract_id = r["Номер контракта"].strip()
                quantity = parse_int(r["Количество"])
                lot = parse_int(r["Лот"])
                amount = parse_money(r["Сумма сделки"])
                delivered = parse_int(r.get("Поставлено", "").strip() or None)
                status = r["Состояние сделки"].strip()

                volume = quantity * lot if (quantity and lot) else 0
                unit_price = amount / volume if (amount and volume) else None
                delivered_volume = delivered * lot if (delivered is not None and lot) else None
                is_annulled = 1 if status == "Аннулирован(Не оплачен)" else 0

                # Lookup contract info
                ci = contract_info.get(contract_id, ("UZS", None, None))
                currency = ci[0]
                tn_ved = ci[1]
                product_category = ci[2]

                rows.append((
                    parse_int(r["Номер сделки"]),
                    parse_date_ddmmyyyy(r["Дата сделки"]),
                    r["Время сделки"].strip(),
                    r["Тип торгов"].strip(),
                    quantity,
                    amount,
                    parse_money(r["Стартовая цена"]),
                    contract_id,
                    r["Наименование товара"].strip(),
                    lot,
                    r["Единица измерения"].strip(),
                    region_uz,
                    REGION_UZ_TO_RU.get(region_uz),
                    r["Тип контракта"].strip(),
                    r["Форма контракта"].strip(),
                    status,
                    r["ИНН продавца"].strip(),
                    r["ИНН покупателя"].strip(),
                    r["Брокер продавца"].strip(),
                    r["Брокер покупателя"].strip(),
                    parse_date_ddmmyyyy(r.get("Дата оплаты", "").strip() or None),
                    parse_date_ddmmyyyy(r.get("Дата поставки", "").strip() or None),
                    delivered,
                    volume,
                    unit_price,
                    currency,
                    delivered_volume,
                    is_annulled,
                    tn_ved,
                    product_category,
                ))
            cur.executemany(
                """INSERT INTO deals (
                    deal_id, deal_date, deal_time, auction_type,
                    quantity, amount, start_price, contract_id,
                    product_name, lot, unit, region_uz, region_ru,
                    contract_type, contract_form, status,
                    seller_inn, buyer_inn, seller_broker, buyer_broker,
                    payment_date, delivery_date, delivered,
                    volume, unit_price, currency, delivered_volume,
                    is_annulled, tn_ved, product_category
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            total += len(rows)
            print(f"  deals_{year}: {len(rows)} rows")

    print(f"  deals total: {total} rows")


def add_derived_columns(conn):
    """Add value_uzs (for export deals) and is_late columns."""
    cur = conn.cursor()

    # Add columns if not exist (ALTER TABLE ADD COLUMN is idempotent-safe in try/except)
    for col, typ in [("value_uzs", "REAL"), ("is_late", "INTEGER DEFAULT 0")]:
        try:
            cur.execute(f"ALTER TABLE deals ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass  # column already exists

    # value_uzs: for export deals, amount * usd_rate on deal_date
    cur.execute("""
        UPDATE deals
        SET value_uzs = deals.amount * usd_rates.rate
        FROM usd_rates
        WHERE deals.currency = 'USD'
          AND deals.deal_date = usd_rates.date
    """)
    affected = cur.rowcount
    print(f"  value_uzs set for {affected} export deals")

    # For UZS deals, value_uzs = amount
    cur.execute("""
        UPDATE deals
        SET value_uzs = amount
        WHERE currency = 'UZS'
    """)
    print(f"  value_uzs set for UZS deals")

    # is_late: delivery_date > payment_date + delivery_days (from contract)
    cur.execute("""
        UPDATE deals
        SET is_late = 1
        WHERE delivery_date IS NOT NULL
          AND payment_date IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM contracts c
              WHERE c.contract_id = deals.contract_id
                AND julianday(deals.delivery_date) > julianday(deals.payment_date) + c.delivery_days
          )
    """)
    affected = cur.rowcount
    print(f"  is_late=1 for {affected} deals")

    conn.commit()


# ────────────────────────────────────────────────────────────────
# Sanity checks
# ────────────────────────────────────────────────────────────────

def run_sanity_checks(conn):
    cur = conn.cursor()
    print("\n=== Sanity Checks ===")

    # Total deals
    cur.execute("SELECT COUNT(*) FROM deals")
    total = cur.fetchone()[0]
    print(f"  Total deals: {total}")
    assert total == 500000, f"Expected 500000, got {total}"

    # Deal ID range
    cur.execute("SELECT MIN(deal_id), MAX(deal_id) FROM deals")
    min_id, max_id = cur.fetchone()
    print(f"  Deal ID range: {min_id} - {max_id}")
    assert min_id == 100001
    assert max_id == 604956

    # Status distribution
    cur.execute("SELECT status, COUNT(*) FROM deals GROUP BY status ORDER BY COUNT(*) DESC")
    print("  Status distribution:")
    for status, cnt in cur.fetchall():
        print(f"    {status}: {cnt}")

    # Deal 247890 exists
    cur.execute("SELECT deal_id, deal_date, product_name, amount FROM deals WHERE deal_id = 247890")
    row = cur.fetchone()
    print(f"  Deal 247890: {row}")
    assert row is not None, "Deal 247890 should exist"

    # Missing deal ID returns nothing
    cur.execute("SELECT * FROM deals WHERE deal_id = 999999")
    assert cur.fetchone() is None, "Deal 999999 should not exist"
    print("  Deal 999999: None (correct)")

    # Contracts count
    cur.execute("SELECT COUNT(*) FROM contracts")
    cnt = cur.fetchone()[0]
    print(f"  Contracts: {cnt}")
    assert cnt == 6616

    # Participants count
    cur.execute("SELECT COUNT(*) FROM participants")
    cnt = cur.fetchone()[0]
    print(f"  Participants: {cnt}")
    assert cnt == 14392

    # Brokers count
    cur.execute("SELECT COUNT(*) FROM brokers")
    cnt = cur.fetchone()[0]
    print(f"  Brokers: {cnt}")
    assert cnt == 120

    # USD rates count
    cur.execute("SELECT COUNT(*) FROM usd_rates")
    cnt = cur.fetchone()[0]
    print(f"  USD rates: {cnt}")
    assert cnt == 1765

    # Annulled
    cur.execute("SELECT COUNT(*) FROM deals WHERE is_annulled = 1")
    cnt = cur.fetchone()[0]
    print(f"  Annulled deals: {cnt}")
    assert cnt == 33719

    # Export deals
    cur.execute("SELECT COUNT(*) FROM deals WHERE currency = 'USD'")
    cnt = cur.fetchone()[0]
    print(f"  Export deals (USD): {cnt}")
    assert cnt == 6590

    # Late deliveries
    cur.execute("SELECT COUNT(*) FROM deals WHERE is_late = 1")
    cnt = cur.fetchone()[0]
    print(f"  Late deliveries: {cnt}")

    # TN VED codes
    cur.execute("SELECT COUNT(DISTINCT tn_ved) FROM deals WHERE tn_ved IS NOT NULL")
    cnt = cur.fetchone()[0]
    print(f"  Distinct TN VED codes in deals: {cnt}")

    # Check a specific export deal has value_uzs
    cur.execute("SELECT deal_id, amount, currency, value_uzs FROM deals WHERE currency='USD' LIMIT 3")
    print("  Sample export deals with value_uzs:")
    for row in cur.fetchall():
        print(f"    {row}")

    # Regions
    cur.execute("SELECT DISTINCT region_uz FROM deals ORDER BY region_uz")
    regions = [r[0] for r in cur.fetchall()]
    print(f"  Regions (UZ): {len(regions)}")
    assert len(regions) == 14

    print("\n=== All sanity checks passed! ===")


# ────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build UZEX SQLite database")
    parser.add_argument("--data-dir", default="data/raw/uzex_spot_data/uzex_spot_data",
                        help="Path to CSV directory")
    parser.add_argument("--db-path", default="data/uzex.db",
                        help="Output SQLite database path")
    args = parser.parse_args()

    data_dir = os.path.abspath(args.data_dir)
    db_path = os.path.abspath(args.db_path)

    if not os.path.isdir(data_dir):
        print(f"ERROR: Data directory not found: {data_dir}")
        sys.exit(1)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Remove existing DB
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed existing {db_path}")

    print(f"Building database from {data_dir}")
    print(f"Output: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    cur = conn.cursor()

    # Create schema
    cur.executescript(SCHEMA_SQL)
    conn.commit()

    # Load data
    print("\nLoading data...")
    load_brokers(cur, data_dir)
    load_participants(cur, data_dir)
    load_usd_rates(cur, data_dir)
    load_contracts(cur, data_dir)
    conn.commit()

    load_deals(cur, data_dir)
    conn.commit()

    # Derived columns
    print("\nComputing derived columns...")
    add_derived_columns(conn)

    # Indexes
    print("\nCreating indexes...")
    cur.executescript(INDEXES_SQL)
    conn.commit()

    # Sanity checks
    run_sanity_checks(conn)

    # Final stats
    db_size = os.path.getsize(db_path)
    print(f"\nDatabase size: {db_size:,} bytes ({db_size / 1024 / 1024:.1f} MB)")

    conn.close()
    print("Done!")


if __name__ == "__main__":
    main()
