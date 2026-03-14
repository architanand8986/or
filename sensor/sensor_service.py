import time
import random
import threading
from collections import deque

from flask import Flask, jsonify
from prometheus_client import (
    Counter, Gauge, Histogram, Summary,
    generate_latest, CONTENT_TYPE_LATEST,
)

app = Flask(__name__)

SENSOR_EVENTS = deque(maxlen=1000)
REQUEST_COUNT = Counter(
    "sensor_requests_total",
    "Total sensor requests",
    ["endpoint"],
)
CPU_SPIKE_DURATION = Histogram(
    "cpu_spike_duration_seconds",
    "Duration of simulated CPU spike",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)
SENSOR_QUEUE_DEPTH = Gauge(
    "sensor_queue_depth",
    "Current number of events in the sensor queue",
)
SENSOR_TEMPERATURE = Gauge(
    "sensor_temperature_celsius",
    "Current simulated temperature reading",
)
SENSOR_HUMIDITY = Gauge(
    "sensor_humidity_percent",
    "Current simulated humidity reading",
)
PROCESS_LATENCY = Summary(
    "sensor_processing_latency_seconds",
    "Processing time for sensor readings",
)
MEMORY_USAGE_BYTES = Gauge(
    "sensor_memory_usage_bytes",
    "Estimated memory usage of sensor event queue",
)

_metrics_cache = {"data": b"", "expires": 0.0}
_cache_lock = threading.Lock()
CACHE_TTL = 2


def _generate_cached_metrics() -> bytes:
    now = time.monotonic()
    with _cache_lock:
        if now < _metrics_cache["expires"]:
            return _metrics_cache["data"]
        data = generate_latest()
        _metrics_cache["data"] = data
        _metrics_cache["expires"] = now + CACHE_TTL
        return data


def _simulate_sensor():
    while True:
        temperature = round(20.0 + random.uniform(-5, 15), 2)
        humidity = round(40.0 + random.uniform(-10, 30), 2)

        event = {
            "timestamp": time.time(),
            "temperature": temperature,
            "humidity": humidity,
        }
        SENSOR_EVENTS.append(event)

        # Update Prometheus gauges
        SENSOR_TEMPERATURE.set(temperature)
        SENSOR_HUMIDITY.set(humidity)
        SENSOR_QUEUE_DEPTH.set(len(SENSOR_EVENTS))
        MEMORY_USAGE_BYTES.set(len(SENSOR_EVENTS) * 128)
        if random.random() < 0.1:
            with CPU_SPIKE_DURATION.time():
                _cpu_work()

        time.sleep(2)


def _cpu_work():
    total = 0
    for i in range(200_000):
        total += i * i
    return total


@app.route("/metrics")
def metrics():
    REQUEST_COUNT.labels(endpoint="/metrics").inc()
    return _generate_cached_metrics(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


@app.route("/sensor")
def sensor():
    REQUEST_COUNT.labels(endpoint="/sensor").inc()
    with PROCESS_LATENCY.time():
        recent = list(SENSOR_EVENTS)[-10:]
    return jsonify({"status": "ok", "readings": recent})


@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    t = threading.Thread(target=_simulate_sensor, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=8000)
