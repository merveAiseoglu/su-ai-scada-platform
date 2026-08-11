"""
Diagnostic benchmark - 100 concurrent requests.
Captures full 500 body, asyncio slow-callback detection, and pool stats.
"""
import asyncio
import json
import os
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone

import httpx

BASE_URL = os.getenv("BENCH_URL", "http://localhost:8080")
ADMIN_USER = os.getenv("BENCH_USER", "admin@suski.gov.tr")
ADMIN_PASS = os.getenv("BENCH_PASS", "AdminPass123!")
NUM_REQUESTS = int(os.getenv("NUM_REQUESTS", "100"))

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def get_pool_checkedout():
    try:
        with urllib.request.urlopen(f"{BASE_URL}/metrics", timeout=5) as r:
            lines = r.read().decode().splitlines()
        for line in lines:
            if "sqlalchemy_pool_checkedout" in line and not line.startswith("#"):
                return line
        return "(no pool metric found)"
    except Exception as e:
        return f"metrics error: {e}"

async def get_token(client):
    resp = await client.post(
        f"{BASE_URL}/token",
        data={"username": ADMIN_USER, "password": ADMIN_PASS},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

async def make_request(client, token, idx):
    url = f"{BASE_URL}/api/sim/tetikle?istasyon_id=1&mod=karisik"
    start = time.time()
    try:
        resp = await client.post(url, headers={"Authorization": f"Bearer {token}"})
        dur = time.time() - start
        if resp.status_code == 200:
            return {"ok": True, "dur": dur, "idx": idx, "status": 200}
        return {"ok": False, "dur": dur, "idx": idx, "status": resp.status_code, "body": resp.text}
    except httpx.ReadTimeout as e:
        return {"ok": False, "dur": time.time() - start, "idx": idx, "status": "ReadTimeout", "body": str(e)}
    except Exception as e:
        return {"ok": False, "dur": time.time() - start, "idx": idx, "status": type(e).__name__, "body": str(e)}

async def main():
    loop = asyncio.get_event_loop()
    loop.slow_callback_duration = 0.1

    log("=" * 60)
    log(f"DIAGNOSTIC BENCHMARK | {NUM_REQUESTS} concurrent | slow_callback_duration=100ms")
    log("=" * 60)

    log(f"Pool checked-out BEFORE: {get_pool_checkedout()}")

    limits = httpx.Limits(max_connections=NUM_REQUESTS, max_keepalive_connections=NUM_REQUESTS)
    timeout = httpx.Timeout(120.0)

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        try:
            token = await get_token(client)
            log("Auth OK")
        except Exception as e:
            log(f"Auth failed: {e}")
            return

        start = time.time()
        tasks = [make_request(client, token, i) for i in range(NUM_REQUESTS)]
        results = await asyncio.gather(*tasks)
        wall = time.time() - start

    log(f"Pool checked-out AFTER: {get_pool_checkedout()}")

    ok = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]
    log(f"DONE: {len(ok)}/{NUM_REQUESTS} OK in {wall:.1f}s")

    status_counter = Counter(str(r.get("status", "?")) for r in failed)
    log(f"Failure status breakdown: {dict(status_counter)}")

    seen = set()
    log("--- Unique failure bodies ---")
    for r in failed:
        body = r.get("body", "")
        if body not in seen:
            seen.add(body)
            log(f"  [status={r.get('status')}] body={body[:600]}")

    if failed:
        durs = [r["dur"] for r in failed]
        log(f"Failure durations: min={min(durs):.1f}s max={max(durs):.1f}s avg={sum(durs)/len(durs):.1f}s")

    with open("diag_results.json", "w") as f:
        json.dump(results, f, indent=2)
    log("Full results -> diag_results.json")

if __name__ == "__main__":
    asyncio.run(main())
