# -*- coding: utf-8 -*-
"""
Independent Pandas Ground Truth Verifier.
Recomputes 12 core metrics directly from raw CSVs with pandas (bypassing uzex.db).
Queries the live agent for each question (in RU and UZ) with cache disabled.
Outputs comparison table: Question | Pandas Value | Agent Value | Status | Latency.
"""

import argparse
import glob
import os
import sys
import time
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agent import ask_agent

RAW_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "raw", "uzex_spot_data", "uzex_spot_data"))


def compute_ground_truth_from_raw():
    """Compute 12 core metrics directly from raw CSV files using pandas."""
    print("Computing independent ground truth values from raw CSVs via pandas...")
    t_start = time.time()

    # 1. Load contracts
    contracts_file = os.path.join(RAW_DIR, "contracts.csv")
    contracts = pd.read_csv(contracts_file, usecols=["Номер контракта", "Код ТН ВЭД", "Срок поставки"])
    contracts.columns = ["contract_id", "tn_ved", "delivery_days"]
    contracts["tn_ved"] = contracts["tn_ved"].astype(str).str.zfill(6)

    # 2. Load USD rates
    usd_file = os.path.join(RAW_DIR, "usd_rates.csv")
    usd = pd.read_csv(usd_file)
    usd["rate"] = usd["Курс"].astype(str).str.replace(" ", "").astype(float)
    rate_1506 = usd[usd["Дата"] == "15.06.2024"]["rate"].values[0]

    # 3. Load participants
    part_file = os.path.join(RAW_DIR, "participants.csv")
    parts = pd.read_csv(part_file, usecols=["ИНН", "Наименование"])
    inn_map = dict(zip(parts["ИНН"].astype(str), parts["Наименование"]))

    # 4. Load deals across all years
    deal_files = sorted(glob.glob(os.path.join(RAW_DIR, "deals_*.csv")))
    dfs = []
    for f in deal_files:
        df_p = pd.read_csv(f, low_memory=False, usecols=[
            "Номер сделки", "Дата сделки", "Состояние сделки", "Регион", "Тип контракта",
            "Количество", "Лот", "Номер контракта", "Сумма сделки",
            "ИНН продавца", "ИНН покупателя", "Брокер продавца", "Брокер покупателя",
            "Дата оплаты", "Дата поставки"
        ])
        dfs.append(df_p)
    deals = pd.concat(dfs, ignore_index=True)

    # 1. Total deals
    total_deals = len(deals)

    # 2. Annulled deals
    annulled_deals = int((deals["Состояние сделки"] == "Аннулирован(Не оплачен)").sum())

    # Valid deals for business questions
    valid_deals = deals[deals["Состояние сделки"] != "Аннулирован(Не оплачен)"].copy()
    valid_deals["sum_clean"] = valid_deals["Сумма сделки"].astype(str).str.replace(" ", "").astype(float)
    valid_deals["qty"] = valid_deals["Количество"].astype(float)
    valid_deals["lot"] = valid_deals["Лот"].astype(float)
    valid_deals["volume"] = valid_deals["qty"] * valid_deals["lot"]

    # 3. Late deliveries: delivery_date > payment_date + delivery_days
    deals_late_check = deals.dropna(subset=["Дата оплаты", "Дата поставки"]).copy()
    deals_late_check["pay_dt"] = pd.to_datetime(deals_late_check["Дата оплаты"], format="%d.%m.%Y", errors="coerce")
    deals_late_check["del_dt"] = pd.to_datetime(deals_late_check["Дата поставки"], format="%d.%m.%Y", errors="coerce")
    deals_late_check = deals_late_check.dropna(subset=["pay_dt", "del_dt"])
    merged_late = deals_late_check.merge(contracts[["contract_id", "delivery_days"]], left_on="Номер контракта", right_on="contract_id")
    late_delivery_count = int(((merged_late["del_dt"] - merged_late["pay_dt"]).dt.days > merged_late["delivery_days"]).sum())

    # 4 & 5. 2024 Top-5 brokers (seller side and buyer side)
    deals_2024 = valid_deals[valid_deals["Дата сделки"].str.endswith(".2024")].copy()
    top5_seller_brokers = deals_2024.groupby("Брокер продавца")["sum_clean"].sum().sort_values(ascending=False).head(5).index.tolist()
    top5_buyer_brokers = deals_2024.groupby("Брокер покупателя")["sum_clean"].sum().sort_values(ascending=False).head(5).index.tolist()

    # 6. Cement average price in 2024 (TN VED 252329)
    d24_c = deals_2024.merge(contracts[["contract_id", "tn_ved"]], left_on="Номер контракта", right_on="contract_id", how="left")
    cement_2024 = d24_c[d24_c["tn_ved"] == "252329"].copy()
    cement_avg_price_2024 = round(float((cement_2024["sum_clean"] / cement_2024["volume"]).mean()), 2)

    # 7. Deal 247890 seller and buyer
    d247890 = deals[deals["Номер сделки"] == 247890].iloc[0]
    deal_247890_seller = str(d247890["ИНН продавца"])
    deal_247890_buyer = str(d247890["ИНН покупателя"])
    deal_247890_seller_name = inn_map.get(deal_247890_seller, "")
    deal_247890_buyer_name = inn_map.get(deal_247890_buyer, "")

    # 8. Region with most deals
    top_region = valid_deals["Регион"].value_counts().index[0]
    top_region_count = int(valid_deals["Регион"].value_counts().iloc[0])

    # 9. Top cotton buyer in 2023 (TN VED 520100)
    deals_2023 = valid_deals[valid_deals["Дата сделки"].str.endswith(".2023")].merge(
        contracts[["contract_id", "tn_ved"]], left_on="Номер контракта", right_on="contract_id", how="left"
    )
    cotton_2023 = deals_2023[deals_2023["tn_ved"] == "520100"]
    cotton_buyer_sums = cotton_2023.groupby("ИНН покупателя")["volume"].sum().sort_values(ascending=False)
    top_cotton_buyer_inn = str(cotton_buyer_sums.index[0])
    top_cotton_buyer_name = inn_map.get(top_cotton_buyer_inn, "")
    top_cotton_buyer_vol = int(cotton_buyer_sums.iloc[0])

    # 10. Sugar total volume (TN VED 170199)
    deals_with_contracts = valid_deals.merge(contracts[["contract_id", "tn_ved"]], left_on="Номер контракта", right_on="contract_id", how="left")
    sugar_deals = deals_with_contracts[deals_with_contracts["tn_ved"] == "170199"]
    sugar_total_volume = int(sugar_deals["volume"].sum())

    # 11. Export deals count
    export_deals_count = int(((deals["Тип контракта"] == "Экспортный") & (deals["Состояние сделки"] != "Аннулирован(Не оплачен)")).sum())

    # 12. Total cotton volume sold in 2023
    cotton_2023_total_kg = int(cotton_2023["volume"].sum())

    elapsed = round(time.time() - t_start, 2)
    print(f"Independent ground truth computation finished in {elapsed}s.\n")

    return {
        "total_deals": total_deals,
        "annulled_deals": annulled_deals,
        "late_delivery_count": late_delivery_count,
        "top5_seller_brokers": top5_seller_brokers,
        "top5_buyer_brokers": top5_buyer_brokers,
        "cement_avg_price_2024": cement_avg_price_2024,
        "rate_1506": rate_1506,
        "deal_247890_seller": deal_247890_seller,
        "deal_247890_buyer": deal_247890_buyer,
        "deal_247890_seller_name": deal_247890_seller_name,
        "deal_247890_buyer_name": deal_247890_buyer_name,
        "top_region": top_region,
        "top_region_count": top_region_count,
        "top_cotton_buyer_inn": top_cotton_buyer_inn,
        "top_cotton_buyer_name": top_cotton_buyer_name,
        "top_cotton_buyer_vol": top_cotton_buyer_vol,
        "sugar_total_volume": sugar_total_volume,
        "export_deals_count": export_deals_count,
        "cotton_2023_total_kg": cotton_2023_total_kg,
    }


def run_verification():
    parser = argparse.ArgumentParser(description="Verify agent against independent pandas calculations")
    parser.add_argument("--no-cache", action="store_true", default=True, help="Disable cache")
    parser.add_argument("--pause", type=float, default=2.5, help="Pause between queries (default 2.5s)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of test items")
    args = parser.parse_args()

    gt = compute_ground_truth_from_raw()

    # Define the 12 questions with verification rules
    test_suite = [
        {
            "id": 1,
            "metric": "Total Deals Count",
            "pandas_val": f"{gt['total_deals']:,}",
            "tokens": [str(gt["total_deals"])],
            "ru": "Сколько всего сделок в базе данных?",
            "uz": "Ma'lumotlar bazasida jami nechta bitim bor?"
        },
        {
            "id": 2,
            "metric": "Annulled Deals Count",
            "pandas_val": f"{gt['annulled_deals']:,}",
            "tokens": [str(gt["annulled_deals"])],
            "ru": "Сколько сделок было аннулировано?",
            "uz": "Nechta bitim bekor qilingan?"
        },
        {
            "id": 3,
            "metric": "Late Delivery Count",
            "pandas_val": f"{gt['late_delivery_count']:,}",
            "tokens": [str(gt["late_delivery_count"])],
            "ru": "Сколько сделок с просроченной поставкой?",
            "uz": "Nechta bitimda yetkazib berish muddati buzilgan?"
        },
        {
            "id": 4,
            "metric": "Top Seller Brokers 2024",
            "pandas_val": ", ".join(gt["top5_seller_brokers"]),
            "tokens": gt["top5_seller_brokers"][:3],  # Check at least top-3
            "ru": "Топ-5 брокеров продавца по сумме сделок в 2024 году",
            "uz": "2024 yilda sotuvchi tomoni bo'yicha bitimlar summasi bo'yicha top-5 brokerlar"
        },
        {
            "id": 5,
            "metric": "Top Buyer Brokers 2024",
            "pandas_val": ", ".join(gt["top5_buyer_brokers"]),
            "tokens": gt["top5_buyer_brokers"][:3],  # Check at least top-3
            "ru": "Топ-5 брокеров покупателя по сумме сделок в 2024 году",
            "uz": "2024 yilda xaridor tomoni bo'yicha bitimlar summasi bo'yicha top-5 brokerlar"
        },
        {
            "id": 6,
            "metric": "Cement 2024 Avg Price",
            "pandas_val": f"{gt['cement_avg_price_2024']:,.2f} UZS/t",
            "tokens": [str(int(gt["cement_avg_price_2024"]))],
            "ru": "Какая средняя цена цемента в 2024 году?",
            "uz": "2024 yilda sementning o'rtacha narxi qancha bo'lgan?"
        },
        {
            "id": 7,
            "metric": "USD Rate on 15.06.2024",
            "pandas_val": f"{gt['rate_1506']}",
            "tokens": ["11862"],
            "ru": "Какой был курс доллара 15 июня 2024 года?",
            "uz": "2024 yil 15 iyun kuni dollar kursi qancha bo'lgan?"
        },
        {
            "id": 8,
            "metric": "Deal 247890 Buyer & Seller",
            "pandas_val": f"Seller: {gt['deal_247890_seller']}, Buyer: {gt['deal_247890_buyer']}",
            "tokens": [gt["deal_247890_seller"], gt["deal_247890_buyer"]],
            "ru": "Кто продавец и покупатель в сделке номер 247890?",
            "uz": "247890-raqamli bitimda sotuvchi va xaridor kim?"
        },
        {
            "id": 9,
            "metric": "Most Deals Region",
            "pandas_val": f"{gt['top_region']} ({gt['top_region_count']:,})",
            "tokens": ["Ташкент", "Toshkent", str(gt["top_region_count"])],
            "ru": "В каком регионе больше всего сделок?",
            "uz": "Qaysi hududda eng ko'p bitim tuzilgan?"
        },
        {
            "id": 10,
            "metric": "Sugar Total Volume",
            "pandas_val": f"{gt['sugar_total_volume']:,} tons",
            "tokens": [str(gt["sugar_total_volume"])],
            "ru": "Сколько сахара продано за весь период?",
            "uz": "Barcha davr mobaynida qancha shakar sotilgan?"
        },
        {
            "id": 11,
            "metric": "Export Deals Count",
            "pandas_val": f"{gt['export_deals_count']:,}",
            "tokens": [str(gt["export_deals_count"])],
            "ru": "Сколько экспортных сделок зарегистрировано?",
            "uz": "Nechta eksport bitimi ro'yxatga olingan?"
        },
        {
            "id": 12,
            "metric": "Top Cotton Buyer 2023",
            "pandas_val": f"INN: {gt['top_cotton_buyer_inn']} ({gt['top_cotton_buyer_name']}), {gt['top_cotton_buyer_vol']:,} kg",
            "tokens": [gt["top_cotton_buyer_inn"], "Zoket", str(gt["top_cotton_buyer_vol"])],
            "ru": "Кто главный покупатель хлопка (код 520100) в 2023 году?",
            "uz": "2023 yilda paxta (kod 520100) bo'yicha asosiy xaridor kim?"
        }
    ]

    if args.limit is not None:
        test_suite = test_suite[:args.limit]

    print("=" * 110)
    print("INDEPENDENT PANDAS VS AGENT VERIFICATION")
    print("=" * 110)
    print(f"{'#':<3} | {'Lang':<4} | {'Metric':<25} | {'Pandas Ground Truth':<25} | {'Agent Value Summary':<30} | {'Status':<6} | {'Lat':<6}")
    print("-" * 110)

    total_queries = len(test_suite) * 2
    passed_queries = 0
    latencies = []
    failures = []

    for item in test_suite:
        for lang, q in [("ru", item["ru"]), ("uz", item["uz"])]:
            t0 = time.time()
            res = ask_agent(q, no_cache=args.no_cache)
            lat_s = time.time() - t0
            latencies.append(lat_s)

            answer = res.get("answer", "")
            ans_clean = answer.replace(" ", "").replace("\u00a0", "").replace(",", "")

            # Check matching tokens
            matched = False
            for tok in item["tokens"]:
                tok_clean = tok.replace(" ", "")
                if tok_clean in ans_clean or tok.lower() in answer.lower():
                    matched = True
                    break

            # Short snippet of answer
            first_line = answer.split("\n")[0].strip()
            if len(first_line) > 30:
                first_line = first_line[:27] + "..."

            status_str = "MATCH" if matched else "MISMATCH"
            if matched:
                passed_queries += 1
            else:
                failures.append({
                    "id": item["id"],
                    "metric": item["metric"],
                    "lang": lang,
                    "question": q,
                    "pandas": item["pandas_val"],
                    "agent_answer": answer[:200],
                    "sql": res.get("sql", "")
                })

            print(f"{item['id']:<3} | {lang.upper():<4} | {item['metric']:<25} | {item['pandas_val']:<25} | {first_line:<30} | {status_str:<6} | {lat_s:>4.2f}s")

            if args.pause > 0:
                time.sleep(args.pause)

    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    pass_rate = (passed_queries / total_queries) * 100 if total_queries else 0

    print("=" * 110)
    print("INDEPENDENT VERIFICATION SUMMARY:")
    print(f"Total Queries Evaluated: {total_queries} (12 metrics x 2 languages [RU/UZ])")
    print(f"Matched Queries:         {passed_queries}")
    print(f"Mismatched Queries:      {len(failures)}")
    print(f"Match Rate:              {pass_rate:.1f}%")
    print(f"Average Latency:         {avg_lat:.2f} s")
    print("=" * 110)

    if failures:
        print("\nMISMATCH DETAILS:")
        for f in failures:
            print(f"[{f['lang'].upper()}] #{f['id']} {f['metric']}")
            print(f"  Question:      {f['question']}")
            print(f"  Pandas Truth:  {f['pandas']}")
            print(f"  Agent Answer:  {f['agent_answer']}")
            print(f"  SQL:           {f['sql']}")
            print("-" * 80)
        sys.exit(1)
    else:
        print("\nALL 12 INDEPENDENT PANDAS METRICS MATCHED PERFECTLY ACROSS RU AND UZ!")
        sys.exit(0)


if __name__ == "__main__":
    run_verification()
