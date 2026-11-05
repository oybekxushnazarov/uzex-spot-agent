# -*- coding: utf-8 -*-
"""Test 10 NEW free-form Uzbek and Russian questions through the live LLM -> SQL -> Verifier pipeline."""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agent import ask_agent

QUESTIONS = [
    # 5 Uzbek questions
    {"id": 1, "lang": "uz", "q": "2025 yilda qancha suyultirilgan gaz sotilgan?"},
    {"id": 2, "lang": "uz", "q": "Namangan viloyatida 2023 yilda tuzilgan bitimlar soni nechta?"},
    {"id": 3, "lang": "uz", "q": "BK015 brokeri orqali qancha bitim amalga oshirilgan?"},
    {"id": 4, "lang": "uz", "q": "2024 yilda eng ko'p sotilgan 3 ta mahsulot qaysilar?"},
    {"id": 5, "lang": "uz", "q": "2022 yilda o'rtacha benzin narxi qancha bo'lgan?"},
    
    # 5 Russian questions
    {"id": 6, "lang": "ru", "q": "Какова общая сумма сделок по дизельному топливу в 2023 году?"},
    {"id": 7, "lang": "ru", "q": "Сколько сделок было заключено в Самаркандской области в 2024 году?"},
    {"id": 8, "lang": "ru", "q": "Какой объем продовольственной пшеницы был продан за весь период?"},
    {"id": 9, "lang": "ru", "q": "Сколько сделок совершено на экспорт в 2025 году?"},
    {"id": 10, "lang": "ru", "q": "Какова максимальная сумма одной сделки по сахару?"},
]

def main():
    print("=" * 90)
    print("TESTING 10 NEW FREE-FORM QUESTIONS VIA LIVE LLM -> SQL -> VERIFIER PIPELINE")
    print("=" * 90)
    
    results = []
    
    for item in QUESTIONS:
        qid = item["id"]
        lang = item["lang"]
        q = item["q"]
        
        print(f"\n[{qid}/10] [{lang.upper()}] Question: {q}")
        t0 = time.time()
        res = ask_agent(q, session_id=f"test_session_{qid}")
        duration_ms = int((time.time() - t0) * 1000)
        
        sql = res.get("sql", "N/A")
        ans = res.get("answer", "")
        grounded = res.get("grounded", False)
        status = res.get("status", "")
        
        print(f"Generated SQL: {sql}")
        print(f"Status: {status} | Grounded: {grounded} | Latency: {duration_ms} ms")
        print("Answer:")
        print(ans)
        print("-" * 90)
        
        results.append({
            "id": qid,
            "lang": lang,
            "q": q,
            "sql": sql,
            "status": status,
            "grounded": grounded,
            "latency_ms": duration_ms,
            "ans_preview": ans.split('---')[0].strip()
        })
        
        # Brief pause to respect API rate limits smoothly
        time.sleep(1.5)
        
    print("\n" + "=" * 90)
    print("10 NEW QUESTIONS SUMMARY:")
    print(f"{'#':<3} | {'Lang':<4} | {'Status':<10} | {'Grounded':<8} | {'Lat(ms)':<7} | {'Question'}")
    print("-" * 90)
    for r in results:
        print(f"{r['id']:<3} | {r['lang'].upper():<4} | {r['status']:<10} | {str(r['grounded']):<8} | {r['latency_ms']:<7} | {r['q'][:45]}")
    print("=" * 90)

if __name__ == "__main__":
    main()
