# 🚀 Deployment Guide — 24/7 Always-On Public Web Service

## ⚠️ CRITICAL WARNING: Free-Tier Sleeping Hosts
Organizers require responses within **90 seconds** (target < 15s). Free hosting tiers that spin down on inactivity (such as Render Free, Koyeb Free, or HuggingFace Spaces) take **50–85 seconds to cold-boot**, risking immediate disqualification if the jury evaluates during sleep mode.

**Recommended Always-On Options:**
1. **Cloud VM / VPS** ($4–$5/mo on Hetzner, DigitalOcean, Linode, AWS Lightsail).
2. **Railway / Render Paid Tier** (with "Always-On" enabled, no sleeping).
3. **Cloudflare Tunnel from a Dedicated Host**: Run locally on a reliable server/laptop with `cloudflared`.

---

## 3–5 Commands to Go Public

### Option A: Deploy via Docker on Any VPS (Recommended)
```bash
# 1. Clone repository & enter directory
git clone <YOUR_REPO_URL> && cd uzex

# 2. Configure environment (optional Gemini key for extended queries)
cp .env.example .env

# 3. Build & start container in detached mode (always restarts)
docker compose up -d --build

# 4. Verify service is healthy (must show "healthy" and 500,000 deals)
curl http://localhost:8000/api/health
```

### Option B: Instant Public URL with Cloudflare Tunnel (Zero Port-Forwarding)
```bash
# 1. Start local server
python -X utf8 -m uvicorn app.server:app --host 0.0.0.0 --port 8000

# 2. Expose immediately via free Cloudflare Quick Tunnel:
cloudflared tunnel --url http://localhost:8000
# Output will display your permanent public URL (e.g. https://xyz.trycloudflare.com)
```

---

## Database Bundling Strategy
- **Choice**: The pre-built SQLite database (`data/uzex.db`, 407 MB) is bundled directly into the Docker image.
- **Justification**:
  1. Instant container startup (< 1 second cold boot) compared to a 3-minute CSV ETL process.
  2. Guarantees deterministic read-only access without runtime file locks.
  3. Eliminates CSV parsing dependencies and CPU spikes during startup.
