from prometheus_client import Counter, Histogram

# --- Custom Business Metrics ---

anomaly_counter = Counter(
    "su_ai_anomaly_counter",
    "Anomalies detected, labelled by severity",
    ["severity"],  # kritik, uyari, normal, vb.
)

llm_call_counter = Counter(
    "su_ai_llm_call_counter",
    "LLM calls, labelled by provider and result",
    ["provider", "result"],  # provider: openai/ollama, result: success/error
)

llm_latency_histogram = Histogram(
    "su_ai_llm_latency_seconds",
    "LLM response time in seconds, labelled by provider",
    ["provider"],
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0],
)

judge_score_histogram = Histogram(
    "su_ai_judge_score_distribution",
    "LLM-as-Judge scores (0-100), labelled by prompt_version",
    ["prompt_version"],
    buckets=[0, 20, 40, 60, 80, 90, 100],
)

mqtt_message_counter = Counter(
    "su_ai_mqtt_message_counter",
    "MQTT messages received, labelled by status",
    ["status"],  # valid, malformed
)

trend_risk_histogram = Histogram(
    "su_ai_trend_risk_score",
    "Predictive trend risk scores (0-100), labelled by parameter",
    ["parameter"],
    buckets=[0, 20, 40, 60, 80, 100],
)
