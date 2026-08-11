import argparse
import asyncio
import time
import httpx
from datetime import datetime, timezone

parser = argparse.ArgumentParser()
parser.add_argument('--count', type=int, default=500, help='Number of concurrent requests')
args, _ = parser.parse_known_args()

BASE_URL = "http://localhost:8080"
ADMIN_USER = "admin@suski.gov.tr"
ADMIN_PASS = "admin123"
NUM_REQUESTS = args.count

async def get_token(client: httpx.AsyncClient) -> str:
    response = await client.post(
        f"{BASE_URL}/token",
        data={"username": ADMIN_USER, "password": ADMIN_PASS},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    response.raise_for_status()
    return response.json()["access_token"]

async def make_request(client: httpx.AsyncClient, token: str, idx: int):
    url = f"{BASE_URL}/api/sim/tetikle?istasyon_id=1&mod=karisik"
    start_time = time.time()
    try:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}
        )
        duration = time.time() - start_time
        if resp.status_code == 200:
            return {"status": "success", "duration": duration, "idx": idx}
        else:
            return {"status": "error", "duration": duration, "idx": idx, "error": resp.text}
    except Exception as e:
        duration = time.time() - start_time
        return {"status": "error", "duration": duration, "idx": idx, "error": str(e)}

async def run_load_test():
    print(f"Starting load test with {NUM_REQUESTS} concurrent requests...")
    
    limits = httpx.Limits(max_connections=NUM_REQUESTS, max_keepalive_connections=NUM_REQUESTS)
    timeout = httpx.Timeout(60.0)
    
    # Use UTC for Prometheus timestamps
    start_dt = datetime.now(timezone.utc)
    
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        try:
            token = await get_token(client)
        except Exception as e:
            print(f"Failed to get token: {e}")
            return None
        
        tasks = [make_request(client, token, i) for i in range(NUM_REQUESTS)]
        
        # Truly concurrent execution using asyncio.gather
        results = await asyncio.gather(*tasks)
        
    end_dt = datetime.now(timezone.utc)
    
    # Analyze results
    successes = [r for r in results if r["status"] == "success"]
    errors = [r for r in results if r["status"] == "error"]
    latencies = [r["duration"] for r in successes]
    
    total_time = (end_dt - start_dt).total_seconds()
    
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    
    latencies.sort()
    p95_lat = latencies[int(len(latencies) * 0.95)] if latencies else 0
    p99_lat = latencies[int(len(latencies) * 0.99)] if latencies else 0
    
    success_rate = (len(successes) / NUM_REQUESTS) * 100
    
    return {
        "start_time": start_dt.timestamp(),
        "end_time": end_dt.timestamp(),
        "total_requests": NUM_REQUESTS,
        "success_count": len(successes),
        "error_count": len(errors),
        "success_rate": success_rate,
        "total_duration": total_time,
        "avg_latency": avg_lat,
        "p95_latency": p95_lat,
        "p99_latency": p99_lat
    }

if __name__ == "__main__":
    result = asyncio.run(run_load_test())
    print(result)
