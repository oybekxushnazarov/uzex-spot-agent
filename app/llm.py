# -*- coding: utf-8 -*-
"""
Provider-agnostic LLM caller with dynamic model discovery, dual API keys,
circuit breaker for 429 RESOURCE_EXHAUSTED, 503 retry-backoff, and fallback chain.
"""

import concurrent.futures
import json
import os
import re
import time
from typing import Optional, Any
from dotenv import load_dotenv

# Load .env file
load_dotenv()

GEMINI_API_KEY_1 = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
GEMINI_API_KEY_2 = os.environ.get("GEMINI_API_KEY_2")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Permanent 404 blacklist (never retry during process lifetime)
PERMANENTLY_SKIPPED_MODELS: set[str] = set()

# Circuit breaker for 429: (model_name, key_tag) -> timestamp until when it is exhausted
EXHAUSTED_UNTIL: dict[tuple[str, str], float] = {}

# Cache of discovered models
DISCOVERED_GEMINI_MODELS: list[str] = []


def get_available_gemini_keys() -> list[tuple[str, str]]:
    """Return list of (key_tag, api_key) for configured Gemini keys."""
    keys = []
    if GEMINI_API_KEY_1:
        keys.append(("key1", GEMINI_API_KEY_1))
    if GEMINI_API_KEY_2:
        keys.append(("key2", GEMINI_API_KEY_2))
    return keys


def discover_available_gemini_models() -> list[str]:
    """Use Google GenAI SDK to list models available to primary API key and sort fast-and-cheap first."""
    global DISCOVERED_GEMINI_MODELS
    if DISCOVERED_GEMINI_MODELS:
        return DISCOVERED_GEMINI_MODELS

    primary_key = GEMINI_API_KEY_1 or GEMINI_API_KEY_2
    if not primary_key:
        return []

    try:
        from google import genai
        client = genai.Client(api_key=primary_key)
        all_models = list(client.models.list())
        
        priority_order = [
            "gemini-3.1-flash-lite",
            "gemini-3-flash-preview",
            "gemini-3.5-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.7-flash",
            "gemini-3.8-flash",
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
            "gemini-3.1-pro-preview",
            "gemini-pro-latest"
        ]
        
        available_names = set()
        for m in all_models:
            name = getattr(m, "name", "") or getattr(m, "model", "")
            clean_name = name.replace("models/", "").strip()
            methods = getattr(m, "supported_generation_methods", []) or getattr(m, "supported_actions", [])
            if "generateContent" in methods:
                available_names.add(clean_name)
                
        ordered = [m for m in priority_order if m in available_names]
        for m in sorted(available_names):
            if m not in ordered and not any(x in m for x in ["tts", "image", "audio", "embedding", "transcribe", "live", "robotics"]):
                ordered.append(m)
                
        print(f"[LLM Discovery] Discovered {len(available_names)} generative models. Selected fallback chain: {ordered[:7]}")
        DISCOVERED_GEMINI_MODELS = ordered
        return ordered
    except Exception as e:
        print(f"[LLM Discovery Warning] Could not list models: {e}")
        fallback_list = [
            "gemini-3.1-flash-lite",
            "gemini-3-flash-preview",
            "gemini-3.5-flash",
            "gemini-3.6-flash",
            "gemini-3.8-flash"
        ]
        DISCOVERED_GEMINI_MODELS = fallback_list
        return fallback_list


def get_configured_model_chain() -> list[str]:
    """Build fallback chain from LLM_MODELS env or auto-discovery, with OpenAI as final fallback."""
    env_models = os.environ.get("LLM_MODELS", "").strip()
    chain = []
    
    if env_models:
        for item in env_models.split(","):
            item = item.strip()
            if item:
                chain.append(item)
    else:
        discovered = discover_available_gemini_models()
        for m in discovered[:6]:
            chain.append(f"gemini:{m}")
            
    if OPENAI_API_KEY and not any(m.startswith("openai:") for m in chain):
        chain.append("openai:gpt-4o-mini")
        
    return chain


def call_gemini_single_key(
    prompt: str,
    system_instruction: str,
    model_name: str,
    api_key: str,
    timeout_sec: float = 18.0
) -> tuple[Optional[dict[str, Any]], Optional[int], str]:
    """
    Call a single Gemini model with a specific API key and per-request timeout.
    Returns: (parsed_json, error_code, error_message)
    """
    from google import genai
    from google.genai import types

    def _execute():
        client = genai.Client(api_key=api_key)
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.0,
            response_mime_type="application/json"
        )
        return client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config
        )

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_execute)
            response = future.result(timeout=timeout_sec)
            
        if response and response.text:
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            parsed = json.loads(text.strip())
            return parsed, None, ""
    except concurrent.futures.TimeoutError:
        return None, 408, f"Request timeout after {timeout_sec}s on model {model_name}"
    except Exception as e:
        err_str = str(e)
        code = getattr(e, "code", None)
        if not code:
            if "404" in err_str:
                code = 404
            elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                code = 429
            elif "503" in err_str or "UNAVAILABLE" in err_str:
                code = 503
            else:
                code = 500
        return None, code, err_str

    return None, 500, "Empty response received"


def call_openai_single(
    prompt: str,
    system_instruction: str,
    model_name: str = "gpt-4o-mini",
    timeout_sec: float = 18.0
) -> tuple[Optional[dict[str, Any]], Optional[int], str]:
    """Call an OpenAI-compatible endpoint with timeout."""
    if not OPENAI_API_KEY:
        return None, 401, "OPENAI_API_KEY not configured"

    import httpx
    url = f"{OPENAI_API_BASE.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }

    try:
        with httpx.Client(timeout=timeout_sec) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content), None, ""
            else:
                return None, resp.status_code, f"OpenAI error: {resp.text}"
    except httpx.TimeoutException:
        return None, 408, f"OpenAI timeout after {timeout_sec}s"
    except Exception as e:
        return None, 500, str(e)


def call_llm_chain(
    prompt: str,
    system_instruction: str,
    total_budget_sec: float = 45.0,
    per_request_timeout: float = 14.0
) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]], str]:
    """
    Execute provider-agnostic fallback chain with:
    - 45s total budget
    - 18s per-request timeout
    - Circuit breaker for 429: skip model on current key for 60s, try secondary key, then skip
    - 503 retry-backoff (up to 2 retries with 2-4s backoff)
    - 404 permanent skip
    Returns: (result_dict_or_None, attempt_logs, used_model_info_str)
    """
    start_time = time.time()
    chain = get_configured_model_chain()
    gemini_keys = get_available_gemini_keys()
    attempt_logs = []

    for entry in chain:
        elapsed = time.time() - start_time
        if elapsed >= total_budget_sec:
            print(f"[LLM Chain] Total budget of {total_budget_sec}s exhausted.")
            break

        parts = entry.split(":", 1)
        provider = parts[0].lower().strip()
        model_name = parts[1].strip() if len(parts) > 1 else ""

        if model_name in PERMANENTLY_SKIPPED_MODELS:
            continue

        if provider == "gemini":
            # Loop over available API keys (key1, key2)
            for key_tag, api_key in gemini_keys:
                now = time.time()
                # Check circuit breaker for this (model, key)
                exhausted_until = EXHAUSTED_UNTIL.get((model_name, key_tag), 0)
                if now < exhausted_until:
                    continue

                # For 503 errors only: allow up to 2 retries with backoff
                max_attempts = 2
                for attempt in range(1, max_attempts + 1):
                    time_remaining = total_budget_sec - (time.time() - start_time)
                    if time_remaining <= 2.0:
                        break

                    current_timeout = min(per_request_timeout, time_remaining)
                    t_call = time.time()

                    parsed, code, err_msg = call_gemini_single_key(
                        prompt=prompt,
                        system_instruction=system_instruction,
                        model_name=model_name,
                        api_key=api_key,
                        timeout_sec=current_timeout
                    )
                    duration_ms = int((time.time() - t_call) * 1000)

                    success = bool(parsed and isinstance(parsed, dict) and "sql" in parsed)
                    attempt_logs.append({
                        "provider": provider,
                        "model": model_name,
                        "key": key_tag,
                        "attempt": attempt,
                        "duration_ms": duration_ms,
                        "code": code,
                        "success": success
                    })

                    # 1. SUCCESS
                    if success:
                        model_info = f"gemini:{model_name} ({key_tag})"
                        print(f"[LLM Chain] SUCCESS with {model_info} in {duration_ms}ms")
                        return parsed, attempt_logs, model_info

                    # 2. 404 NOT_FOUND: skip model permanently across all keys
                    if code == 404:
                        print(f"[LLM Chain] Model {model_name} returned 404. Skipping permanently.")
                        PERMANENTLY_SKIPPED_MODELS.add(model_name)
                        break

                    # 3. 429 RESOURCE_EXHAUSTED: NEVER retry same model on same key!
                    if code == 429:
                        print(f"[LLM Chain] Model {model_name} got 429 on {key_tag}. Circuit breaker active for 60s.")
                        EXHAUSTED_UNTIL[(model_name, key_tag)] = time.time() + 60.0
                        # Break attempt loop on current key; outer key loop will try next key immediately if available
                        break

                    # 4. 503 UNAVAILABLE: retry on same model with backoff (only 503)
                    if code == 503 and attempt < max_attempts:
                        backoff_sec = 1.5 * attempt
                        print(f"[LLM Chain] Model {model_name} got 503. Retrying in {backoff_sec:.1f}s...")
                        time.sleep(backoff_sec)
                    else:
                        # 408 Timeout or other error: do not retry this key, move to next key/model
                        break

        elif provider == "openai":
            time_remaining = total_budget_sec - (time.time() - start_time)
            if time_remaining <= 2.0:
                break
            current_timeout = min(per_request_timeout, time_remaining)
            t_call = time.time()
            parsed, code, err_msg = call_openai_single(
                prompt=prompt,
                system_instruction=system_instruction,
                model_name=model_name or "gpt-4o-mini",
                timeout_sec=current_timeout
            )
            duration_ms = int((time.time() - t_call) * 1000)
            success = bool(parsed and isinstance(parsed, dict) and "sql" in parsed)
            attempt_logs.append({
                "provider": "openai",
                "model": model_name,
                "duration_ms": duration_ms,
                "code": code,
                "success": success
            })
            if success:
                model_info = f"openai:{model_name}"
                print(f"[LLM Chain] SUCCESS with {model_info} in {duration_ms}ms")
                return parsed, attempt_logs, model_info

    # Secondary recovery: If all models are currently in circuit breaker but total budget remains,
    # wait for the earliest rate-limit timer to expire and attempt call
    time_remaining = total_budget_sec - (time.time() - start_time)
    if time_remaining > 6.0:
        now = time.time()
        active_exhaustions = [exp for exp in EXHAUSTED_UNTIL.values() if exp > now]
        if active_exhaustions:
            earliest_expiry = min(active_exhaustions)
            wait_sec = earliest_expiry - now + 0.5
            if 0 < wait_sec <= (time_remaining - 4.0):
                print(f"[LLM Chain] All models rate-limited. Waiting {wait_sec:.1f}s for circuit breaker recovery...")
                time.sleep(wait_sec)
                for entry in chain:
                    parts = entry.split(":", 1)
                    p = parts[0].lower().strip()
                    m = parts[1].strip() if len(parts) > 1 else ""
                    if p == "gemini" and m not in PERMANENTLY_SKIPPED_MODELS:
                        for key_tag, api_key in gemini_keys:
                            if time.time() >= EXHAUSTED_UNTIL.get((m, key_tag), 0):
                                rem = total_budget_sec - (time.time() - start_time)
                                if rem > 2.0:
                                    parsed, code, err_msg = call_gemini_single_key(
                                        prompt=prompt,
                                        system_instruction=system_instruction,
                                        model_name=m,
                                        api_key=api_key,
                                        timeout_sec=min(per_request_timeout, rem)
                                    )
                                    if parsed and isinstance(parsed, dict) and "sql" in parsed:
                                        model_info = f"gemini:{m} ({key_tag})"
                                        print(f"[LLM Chain] SUCCESS on recovery with {model_info}")
                                        return parsed, attempt_logs, model_info

    return None, attempt_logs, ""
