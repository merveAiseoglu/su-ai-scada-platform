import httpx
import json
from datetime import datetime, timezone

PROM_URL = "http://localhost:9090/api/v1/query"

def query_prometheus(query: str, time_ts: float):
    resp = httpx.get(PROM_URL, params={"query": query, "time": time_ts})
    resp.raise_for_status()
    return resp.json()

def run_investigation():
    now = datetime.now(timezone.utc).timestamp()
    
    print("=== 1. Anomaly Counter Raw Data ===")
    res1 = query_prometheus("su_ai_anomaly_counter_total", now)
    print(json.dumps(res1, indent=2))
    
    print("\n=== 2. LLM Latency Raw Data ===")
    res2_sum = query_prometheus("su_ai_llm_latency_seconds_sum", now)
    res2_count = query_prometheus("su_ai_llm_latency_seconds_count", now)
    print("SUM:", json.dumps(res2_sum, indent=2))
    print("COUNT:", json.dumps(res2_count, indent=2))
    
    print("\n=== 3. HTTP Request Buckets Raw Data ===")
    res3 = query_prometheus("sum(http_request_duration_seconds_bucket) by (le)", now)
    print(json.dumps(res3, indent=2))

if __name__ == "__main__":
    run_investigation()
