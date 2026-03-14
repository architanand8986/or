import time
import random
from flask import Flask, jsonify
from prometheus_client import Counter, Gauge, Histogram, generate_latest

app = Flask(__name__)

data_blob = "X" * 5_000_000

REQUEST_COUNT = Counter("sensor_requests_total", "Total sensor requests")
CPU_SPIKE = Gauge("sensor_cpu_spike", "Simulated CPU spike state")
PROCESS_LATENCY = Histogram("sensor_processing_latency_seconds", "Processing time")

@app.route("/metrics")
def metrics():
    start = time.time()
    for _ in range(2000000):
        pass
    temp_data = data_blob * random.randint(1, 3)
    PROCESS_LATENCY.observe(time.time() - start)
    CPU_SPIKE.set(random.randint(0, 1))
    REQUEST_COUNT.inc()
    return generate_latest()

@app.route("/sensor")
def sensor():
    if random.random() < 0.2:
        return jsonify({"data": data_blob})
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
