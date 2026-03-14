"""
Load test script for the Edge Sensor Service.
"""

import argparse
import time
import threading
import statistics
import urllib.request
import urllib.error


def make_request(url: str) -> tuple[int, float]:
    start = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            resp.read()
            return resp.status, time.monotonic() - start
    except urllib.error.HTTPError as e:
        return e.code, time.monotonic() - start
    except Exception:
        return 0, time.monotonic() - start


def worker(url: str, results: list, stop_event: threading.Event):
    while not stop_event.is_set():
        status, latency = make_request(url)
        results.append((status, latency))
        time.sleep(0.05)


def run_phase(name: str, url: str, concurrency: int, duration: int):
    print(f"\n{'='*60}")
    print(f"Phase: {name}")
    print(f"  URL:         {url}")
    print(f"  Concurrency: {concurrency}")
    print(f"  Duration:    {duration}s")
    print(f"{'='*60}")

    results: list[tuple[int, float]] = []
    stop = threading.Event()
    threads = []

    for _ in range(concurrency):
        t = threading.Thread(target=worker, args=(url, results, stop))
        t.start()
        threads.append(t)

    time.sleep(duration)
    stop.set()
    for t in threads:
        t.join()

    if not results:
        print("  No results collected.")
        return

    latencies = [r[1] for r in results]
    successes = sum(1 for r in results if 200 <= r[0] < 300)
    errors = len(results) - successes

    print(f"\n  Total requests:  {len(results)}")
    print(f"  Successful:      {successes}")
    print(f"  Errors:          {errors}")
    print(f"  Avg latency:     {statistics.mean(latencies):.4f}s")
    print(f"  P50 latency:     {statistics.median(latencies):.4f}s")
    print(f"  P95 latency:     {sorted(latencies)[int(len(latencies)*0.95)]:.4f}s")
    print(f"  P99 latency:     {sorted(latencies)[int(len(latencies)*0.99)]:.4f}s")
    print(f"  Max latency:     {max(latencies):.4f}s")
    print(f"  Throughput:      {len(results)/duration:.1f} req/s")


def main():
    parser = argparse.ArgumentParser(description="Edge sensor load test")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of sensor service")
    parser.add_argument("--duration", type=int, default=30, help="Duration per test phase in seconds")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of concurrent workers")
    args = parser.parse_args()

    base = args.url.rstrip("/")

    print("Edge Sensor Service — Load Test")
    print(f"Base URL: {base}")

    run_phase(
        "Sensor endpoint — normal load",
        f"{base}/sensor",
        concurrency=args.concurrency,
        duration=args.duration,
    )

    run_phase(
        "Metrics endpoint — scrape simulation",
        f"{base}/metrics",
        concurrency=args.concurrency,
        duration=args.duration,
    )

    run_phase(
        "Burst — high concurrency",
        f"{base}/sensor",
        concurrency=args.concurrency * 4,
        duration=min(args.duration, 15),
    )

    print(f"\n{'='*60}")
    print("Load test complete.")
    print("Run 'docker stats' in another terminal to observe resource usage.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
