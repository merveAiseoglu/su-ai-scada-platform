import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

def generate_html(load_test_data, prom_data):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(REPORTS_DIR, f"benchmark_{date_str}.html")
    
    # Fill missing or NaN prometheus data gracefully
    llm_prom = prom_data.get('avg_llm_latency_prom', 0.0)
    import math
    if math.isnan(llm_prom):
        llm_prom = 0.0
        
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
            h1 {{ color: #2C3E50; border-bottom: 2px solid #3498DB; padding-bottom: 10px; }}
            h2 {{ color: #2980B9; margin-top: 30px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            th, td {{ border: 1px solid #BDC3C7; padding: 12px; text-align: left; }}
            th {{ background-color: #ECF0F1; color: #2C3E50; font-weight: bold; }}
            .summary-box {{ background-color: #E8F8F5; border-left: 5px solid #1ABC9C; padding: 15px; margin: 20px 0; font-size: 1.1em; }}
        </style>
    </head>
    <body>
        <h1>Su-AI SCADA - Benchmark Report</h1>
        <p><strong>Date:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        
        <div class="summary-box">
            The system processed {load_test_data['total_requests']} sensors in {load_test_data['total_duration']:.2f} seconds with {load_test_data['success_rate']:.1f}% success rate.
        </div>
        
        <h2>Load Test Application Metrics</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Total Requests</td><td>{load_test_data['total_requests']}</td></tr>
            <tr><td>Successful Requests</td><td>{load_test_data['success_count']}</td></tr>
            <tr><td>Failed Requests</td><td>{load_test_data['error_count']}</td></tr>
            <tr><td>Average Response Time</td><td>{load_test_data['avg_latency']:.3f} s</td></tr>
            <tr><td>P95 Response Time</td><td>{load_test_data['p95_latency']:.3f} s</td></tr>
            <tr><td>P99 Response Time</td><td>{load_test_data['p99_latency']:.3f} s</td></tr>
        </table>
        
        <h2>Prometheus Observability Metrics</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr>
                <td>HTTP P95 Latency (Prometheus)</td>
                <td>{prom_data.get('http_p95_latency_prom', 0.0):.3f} s <br><small><i>Note: Max configured bucket is 1.0s. Values exactly 1.0s indicate real p95 > 1.0s.</i></small></td>
            </tr>
            <tr>
                <td>Average LLM Response Time</td>
                <td>{llm_prom:.3f} s <br><small><i>Based on {prom_data.get('llm_calls_completed', 0):.0f} completed calls (Fallback to Ollama).</i></small></td>
            </tr>
            <tr>
                <td>Total Anomalies Detected</td>
                <td>{prom_data.get('total_anomalies_detected', 0.0):.0f}</td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    return output_path
