import asyncio
import time
from benchmark.load_test import run_load_test
from benchmark.prometheus_query import fetch_metrics
from benchmark.report_generator import generate_html

async def main():
    print("==================================================")
    print("   Su-AI Benchmark Suite")
    print("==================================================")
    
    print("\n[1/4] Running load test (500 concurrent requests)...")
    load_test_results = await run_load_test()
    if not load_test_results:
        print("Load test failed.")
        return
        
    print(f"Load test finished in {load_test_results['total_duration']:.2f} seconds.")
    
    print("\n[2/4] Polling Prometheus to allow LLM queue to drain (max 4 minutes)...")
    
    last_count = -1
    stable_count = 0
    max_wait = 240
    start_wait = time.time()
    eval_time = load_test_results["end_time"]
    prom_data = {}
    
    while time.time() - start_wait < max_wait:
        time.sleep(10)
        eval_time = time.time()
        prom_data = fetch_metrics(load_test_results["start_time"], eval_time)
        current_count = prom_data.get("llm_calls_completed", 0)
        
        print(f"  ... {int(time.time()-start_wait)}s elapsed. LLM calls completed: {current_count}")
        
        if current_count > 0 and current_count == last_count:
            stable_count += 1
            if stable_count >= 2:
                print("  LLM processing queue appears drained!")
                break
        else:
            stable_count = 0
            
        last_count = current_count
        
    print("\n[3/4] Fetching final observability metrics from Prometheus...")
    print(f"Fetched metrics: {prom_data}")
    
    print("\n[4/4] Generating HTML report...")
    output_path = generate_html(load_test_results, prom_data)
    
    print(f"\nReport generated: {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
