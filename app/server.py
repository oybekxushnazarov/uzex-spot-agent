# -*- coding: utf-8 -*-
"""FastAPI web service for UZEX Commodity Exchange Spot Data AI Agent."""

import os
import sys
import time
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Ensure root path is accessible
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agent import ask_agent, DB_PATH
import sqlite3

START_TIME = time.time()

app = FastAPI(
    title="UZEX Spot Data AI Agent",
    description="Deterministic and Grounded AI Assistant for Uzbekistan Commodity Exchange (UZEX)",
    version="1.0.0"
)

# Static files directory
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
os.makedirs(STATIC_DIR, exist_ok=True)

# Simple in-memory sliding window rate limiter
RATE_LIMIT_STORE: dict[str, list[float]] = {}
RATE_LIMIT_MAX = 60  # requests per minute
RATE_LIMIT_WINDOW = 60.0  # seconds


def check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    timestamps = RATE_LIMIT_STORE.get(client_ip, [])
    # Filter timestamps within current window
    valid_ts = [ts for ts in timestamps if now - ts < RATE_LIMIT_WINDOW]
    if len(valid_ts) >= RATE_LIMIT_MAX:
        return False
    valid_ts.append(now)
    RATE_LIMIT_STORE[client_ip] = valid_ts
    return True


class AskRequest(BaseModel):
    question: str = Field(..., max_length=2000, description="Question in Uzbek or Russian")
    session_id: Optional[str] = Field("default", description="Session ID for conversational memory")
    no_cache: Optional[bool] = Field(False, description="Whether to bypass pipeline cache")
    lang: Optional[str] = Field(None, description="Optional language preference ('uz' or 'ru')")


class AskResponse(BaseModel):
    answer: str
    sql: str
    evidence: dict
    latency_ms: int
    grounded: bool
    lang: str


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
        return HTMLResponse("<h1>UZEX AI Agent API is running. index.html not found.</h1>")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/ask", response_model=AskResponse)
async def api_ask(req: AskRequest, request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Maximum 60 requests per minute."
        )
        
    res = ask_agent(
        question=req.question,
        session_id=req.session_id or "default",
        no_cache=bool(req.no_cache),
        lang_hint=req.lang
    )
    return AskResponse(
        answer=res["answer"],
        sql=res.get("sql", ""),
        evidence=res.get("evidence", {}),
        latency_ms=res.get("latency_ms", 0),
        grounded=res.get("grounded", True),
        lang=res.get("lang", "ru")
    )


@app.get("/api/health")
async def api_health():
    uptime_sec = int(time.time() - START_TIME)
    
    # Check DB accessibility & row count
    db_ok = False
    total_deals = 0
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM deals")
        total_deals = cur.fetchone()[0]
        conn.close()
        db_ok = True
    except Exception as e:
        db_err = str(e)
        
    return {
        "status": "healthy" if db_ok else "degraded",
        "service": "UZEX AI Hackathon Spot Data Agent",
        "version": "1.0.0",
        "database_connected": db_ok,
        "database_path": DB_PATH,
        "total_deals_loaded": total_deals,
        "uptime_seconds": uptime_sec,
        "timestamp": time.time()
    }


# Mount static assets if any
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting server on http://{host}:{port}")
    uvicorn.run("app.server:app", host=host, port=port, reload=False)
