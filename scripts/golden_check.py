# -*- coding: utf-8 -*-
"""
Run golden evaluation end-to-end (LLM -> SQL -> Verifier) with cache DISABLED.
Verifies real pipeline accuracy, grounding, and latency.
Exits with code 1 if ANY case fails.
"""

import argparse
import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agent import ask_agent

GOLDEN_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tests", "golden.jsonl"))

TRAP_MARKERS = [
    "mavjud emas", "отсутств", "не торгуется", "sotilmaydi",
    "chetlab o'tish", "обхода инструкций", "prognoz", "прогноз",
    "topilmadi", "не найдено", "tashqarida", "пределами", "qoidalarni",
    "no_data", "refused"
]


def evaluate():
    parser = argparse.ArgumentParser(description="Golden test suite runner")
    parser.add_argument("--no-cache", action="store_true", default=True, help="Disable pipeline cache (default: True)")
    parser.add_argument("--use-cache", dest="no_cache", action="store_false", help="Enable pipeline cache")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of test cases to run")
    parser.add_argument("--offset", type=int, default=0, help="Offset starting test case index")
    parser.add_argument("--pause", type=float, default=4.0, help="Pause between queries in seconds (default: 4.0s)")
    args = parser.parse_args()

    if args.no_cache:
        os.environ["CACHE_ENABLED"] = "0"

    if not os.path.exists(GOLDEN_FILE):
        print(f"Error: {GOLDEN_FILE} not found!")
        sys.exit(1)

    with open(GOLDEN_FILE, "r", encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    if args.offset > 0:
        cases = cases[args.offset:]
    if args.limit is not None:
        cases = cases[:args.limit]

    print("=" * 90)
    print(f"UZEX GOLDEN TEST SUITE — LIVE PIPELINE EVALUATION")
    print(f"Test cases:     {len(cases)}")
    print(f"Cache enabled:   {not args.no_cache}")
    print(f"Inter-query lag: {args.pause}s")
    print("=" * 90)
    print(f"{'#':<3} | {'Lang':<4} | {'Category':<16} | {'Status':<6} | {'Latency':<7} | {'Question'}")
    print("-" * 90)

    passed = 0
    failed = 0
    latencies = []
    failed_details = []

    for idx, c in enumerate(cases, 1):
        q = c["question"]
        lang = c["lang"]
        cat = c["category"]
        is_trap = c.get("is_trap", False)
        expected = c.get("expected_answer", "")

        t0 = time.time()
        res = ask_agent(q, no_cache=args.no_cache)
        lat_s = time.time() - t0
        latencies.append(lat_s)

        answer = res.get("answer", "")
        sql = res.get("sql", "")
        status = res.get("status", "")
        ans_lower = answer.lower()

        case_passed = True
        reasons = []

        # 1. Pipeline status check
        if status in ("SQL_ERROR", "LLM_ERROR", "VALIDATION_ERROR"):
            case_passed = False
            reasons.append(f"Agent returned error status: {status}")

        # 2. Trap check
        if is_trap:
            if status in ("REFUSED", "OUT_OF_DATA", "NO_DATA"):
                case_passed = True
            elif any(m in ans_lower for m in TRAP_MARKERS):
                case_passed = True
            else:
                case_passed = False
                reasons.append("Trap failed: Expected refusal / out-of-data notice")
        else:
            # 3. Ground truth numeric verification
            gt_rows = c.get("ground_truth_rows", [])
            if gt_rows:
                first_row = gt_rows[0]
                for val in first_row:
                    if val is None:
                        continue
                    try:
                        f_val = float(str(val).replace(" ", ""))
                        if f_val >= 100.0:
                            s_int = str(int(f_val))
                            ans_compact = answer.replace(" ", "").replace("\u00a0", "").replace(",", "")
                            if s_int not in ans_compact:
                                case_passed = False
                                reasons.append(f"Missing expected number {s_int}")
                                break
                    except ValueError:
                        pass

        if case_passed:
            passed += 1
            status_str = "PASS"
        else:
            failed += 1
            status_str = "FAIL"
            failed_details.append({
                "index": idx,
                "question": q,
                "expected": expected,
                "actual": answer[:250],
                "sql": sql,
                "reasons": reasons,
                "latency": f"{lat_s:.2f}s"
            })

        print(f"{idx:<3} | {lang.upper():<4} | {cat:<16} | {status_str:<6} | {lat_s:>5.2f}s | {q[:40]}")
        if not case_passed:
            print(f"    --> Expected: {expected[:70]}")
            print(f"    --> Got:      {answer[:80]}...")
            if reasons:
                print(f"    --> Reasons:  {reasons}")
            if sql:
                print(f"    --> SQL:      {sql[:100]}...")

        if idx < len(cases) and args.pause > 0:
            time.sleep(args.pause)

    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    max_lat = max(latencies) if latencies else 0
    pass_rate = (passed / len(cases)) * 100 if cases else 0

    print("=" * 90)
    print("GOLDEN SUITE EVALUATION SUMMARY:")
    print(f"Total Cases:     {len(cases)}")
    print(f"Passed:          {passed}")
    print(f"Failed:          {failed}")
    print(f"Pass Rate:       {pass_rate:.1f}%")
    print(f"Average Latency: {avg_lat:.2f} s")
    print(f"Max Latency:     {max_lat:.2f} s (Target: < 15.0 s, Hard Limit: 90.0 s)")
    print("=" * 90)

    if failed > 0:
        print("\nFAILED CASES BREAKDOWN:")
        for fd in failed_details:
            print("-" * 80)
            print(f"Case #{fd['index']}: {fd['question']}")
            print(f"Expected: {fd['expected']}")
            print(f"Actual:   {fd['actual']}")
            print(f"SQL:      {fd['sql']}")
            print(f"Reasons:  {fd['reasons']}")
        print("\nRESULT: FAILED (Exit Code 1)")
        sys.exit(1)
    else:
        print("\nRESULT: SUCCESS — ALL GOLDEN CASES PASSED!")
        sys.exit(0)


if __name__ == "__main__":
    evaluate()
