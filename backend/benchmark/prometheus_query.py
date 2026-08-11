import httpx

PROM_URL = "http://localhost:9090/api/v1/query"

def query_prometheus(query: str, time_ts: float):
    # time parameter specifies the evaluation instant
    try:
        resp = httpx.get(PROM_URL, params={"query": query, "time": time_ts})
        resp.raise_for_status()
        data = resp.json()
        if data["status"] == "success" and data["data"]["result"]:
            # Extract the value from the first result
            return float(data["data"]["result"][0]["value"][1])
        return 0.0
    except Exception as e:
        print(f"Prometheus query failed for {query}: {e}")
        return 0.0

def fetch_metrics(start_ts: float, end_ts: float):
    # 1. Total anomalies detected (exact count diff)
    anomaly_query = 'sum(su_ai_anomaly_counter_total{severity!="NORMAL"})'
    start_anomalies = query_prometheus(anomaly_query, start_ts)
    end_anomalies = query_prometheus(anomaly_query, end_ts)
    anomalies = max(0.0, end_anomalies - start_anomalies)
    
    # 2. Average LLM latency
    start_llm_sum = query_prometheus('sum(su_ai_llm_latency_seconds_sum)', start_ts)
    end_llm_sum = query_prometheus('sum(su_ai_llm_latency_seconds_sum)', end_ts)
    llm_sum = max(0.0, end_llm_sum - start_llm_sum)
    
    start_llm_count = query_prometheus('sum(su_ai_llm_latency_seconds_count)', start_ts)
    end_llm_count = query_prometheus('sum(su_ai_llm_latency_seconds_count)', end_ts)
    llm_count = max(0.0, end_llm_count - start_llm_count)
    
    llm_avg = (llm_sum / llm_count) if llm_count > 0 else 0.0
    
    # 3. HTTP Request p95 latency
    http_p95_query = 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))'
    http_p95 = query_prometheus(http_p95_query, end_ts)
    
    return {
        "total_anomalies_detected": anomalies,
        "avg_llm_latency_prom": llm_avg,
        "http_p95_latency_prom": http_p95,
        "llm_calls_completed": llm_count
    }
