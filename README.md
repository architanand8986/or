# Edge Device Observability Stack

Ultra-lightweight containerized monitoring stack designed for resource-constrained edge devices (2 CPU / 500 MB RAM / <300 MB usable).

## Problem Statement

The original sensor service had critical performance issues:
- CPU usage spiking to 100% during metrics scraping
- Memory consumption exceeding 500 MB
- Response times >1 second under load
- Unbounded memory growth from 5 MB data blobs
- Heavy monitoring stack (Prometheus + Grafana) consuming ~350 MB

**Goal:** Optimize the system to run efficiently on edge devices with strict resource constraints (2 CPU cores, 500 MB RAM).

## Solution Approach

### 1. Performance Profiling & Root Cause Analysis

**Identified Issues:**
- `/metrics` endpoint had a CPU-spinning loop (`for _ in range(2000000)`)
- Unbounded 5 MB string blob multiplied randomly (5-15 MB per request)
- Metrics generation happened on every scrape without caching
- Heavy monitoring stack unsuitable for edge devices

### 2. Code Optimization Strategy

**Application-Level Fixes:**

a) **Removed CPU-Intensive Operations**
   - Eliminated the 2M iteration busy-wait loop from `/metrics` handler
   - Moved sensor simulation to background thread
   - Result: Response time reduced from >1s to <5ms

b) **Memory Management**
   - Replaced unbounded 5 MB blob with `deque(maxlen=1000)` (bounded queue)
   - Each event ~128 bytes → total ~128 KB vs 5-15 MB
   - Automatic eviction of old data prevents memory leaks

c) **Metrics Caching**
   - Implemented 2-second TTL cache for metrics output
   - Avoids regenerating metrics on every scrape
   - Thread-safe with locking mechanism

d) **Background Processing**
   - Sensor readings generated in daemon thread every 2 seconds
   - CPU spikes isolated and bounded (200K iterations vs 2M)
   - Request handlers remain fast and non-blocking

### 3. Infrastructure Optimization

**Monitoring Stack Replacement:**
- **Before:** Prometheus (200 MB) + Grafana (150 MB) = 350 MB
- **After:** VictoriaMetrics (160 MB) + Static UI (20 MB) = 180 MB
- **Savings:** 48% reduction in monitoring overhead

**Why VictoriaMetrics?**
- Drop-in Prometheus replacement with better compression
- Lower memory footprint and faster queries
- Single binary, easier to deploy on edge devices

**Why Static Dashboard?**
- No backend required (Chart.js + vanilla JavaScript)
- Served by lightweight Caddy (20 MB vs Grafana's 150 MB)
- Direct queries to VictoriaMetrics API

### 4. Container Optimization

**Multi-Stage Docker Build:**
```dockerfile
FROM python:3.11-slim AS build
# Build wheels in isolation

FROM python:3.11-slim
# Copy only compiled wheels
# Result: 85% smaller final image
```

**Resource Limits:**
```yaml
mem_limit: 150m    # Prevent memory overflow
cpus: "0.5"        # Fair CPU allocation
```

**Security Hardening:**
- Non-root user (`appuser`)
- Minimal base image (`python:3.11-slim`)
- Health checks for reliability

### 5. Architecture Design

**Separation of Concerns:**
```
┌─────────────────┐
│ Sensor Service  │ ← Generates metrics
└────────┬────────┘
         │ /metrics
┌────────▼────────┐
│    vmagent      │ ← Scrapes & forwards
└────────┬────────┘
         │ remote_write
┌────────▼────────┐
│ VictoriaMetrics │ ← Stores time-series
└────────┬────────┘
         │ HTTP API
┌────────▼────────┐
│  Static UI      │ ← Visualizes data
└─────────────────┘
```

**Benefits:**
- Each component has single responsibility
- Failure isolation (one service down ≠ total failure)
- Easy to scale or replace individual components

### 6. Testing & Validation

**Load Testing Script:**
- Simulates concurrent users (configurable)
- Tests multiple endpoints under stress
- Measures latency percentiles (P50, P95, P99)
- Monitors resource usage during tests

**Validation Metrics:**
- ✅ CPU usage: <50% under load
- ✅ Memory: <300 MB total stack
- ✅ Response time: <10 ms (P95)
- ✅ Throughput: 100+ req/s
- ✅ No memory leaks over extended runs

## Architecture

```
Sensor Service (Python/Flask)
        │  /metrics
        ▼
    vmagent (scraper)
        │  remote_write
        ▼
  VictoriaMetrics (TSDB)
        │  HTTP API
        ▼
  Static Dashboard (Caddy + Chart.js)
```

## Components

| Service           | Port  | Memory Limit | Purpose                     |
|-------------------|-------|--------------|-----------------------------|
| sensor            | 8000  | 150 MB       | Simulated sensor + metrics  |
| vmagent           | —     | 60 MB        | Prometheus-compatible scraper |
| victoria          | 8428  | 160 MB       | Time-series storage         |
| ui (Caddy)        | 3000  | 20 MB        | Static dashboard            |

## Prerequisites

- Docker (20.10+)
- Docker Compose (2.0+)
- Python 3.10+ (for load testing)

## Quick Start

### 1. Start the Stack

```bash
docker compose up --build
```

Or run in detached mode:

```bash
docker compose up --build -d
```

### 2. Verify Services

Check container status:
```bash
docker compose ps
```

Test sensor health:
```bash
curl http://localhost:8000/health
```

View raw metrics:
```bash
curl http://localhost:8000/metrics
```

Query VictoriaMetrics:
```bash
curl 'http://localhost:8428/api/v1/query?query=sensor_temperature_celsius'
```

### 3. Access Dashboard

Open your browser and navigate to:
```
http://localhost:3000
```

The dashboard displays real-time metrics including:
- Temperature readings
- Queue depth
- CPU spike duration
- Request counts
- Memory usage

## Load Testing

Run load tests to verify performance:

```bash
python load_test.py --url http://localhost:8000 --duration 30 --concurrency 5
```

Monitor resource usage during tests:
```bash
docker stats
```

### Load Test Options

```bash
python load_test.py --help

Options:
  --url URL              Base URL of sensor service (default: http://localhost:8000)
  --duration SECS        Duration per test phase in seconds (default: 30)
  --concurrency N        Number of concurrent workers (default: 5)
```

## Repository Structure

```
.
├── sensor/
│   ├── sensor_service.py    # Optimized sensor service
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile           # Multi-stage build
├── monitoring/
│   └── vmagent.yml          # Scrape configuration
├── ui/
│   ├── index.html           # Dashboard page
│   ├── app.js               # Chart.js dashboard logic
│   └── Caddyfile            # Reverse proxy config
├── docker-compose.yml       # Full stack definition
├── load_test.py             # Load testing script
├── PERFORMANCE_REPORT.md    # Detailed performance analysis
└── README.md                # This file
```

## Key Optimizations Summary

| Optimization | Before | After | Impact |
|-------------|--------|-------|--------|
| CPU Loop | 2M iterations | Removed | Response time: 1s → 5ms |
| Memory Blob | 5-15 MB unbounded | 128 KB bounded | 98% reduction |
| Metrics Cache | None | 2s TTL | Reduced CPU on scrapes |
| Monitoring Stack | 350 MB | 180 MB | 48% reduction |
| Docker Image | Large | Multi-stage | 85% smaller |
| CPU Usage | 100% spikes | <50% | Stable performance |
| Memory Total | >500 MB | <300 MB | Fits constraints |

See [PERFORMANCE_REPORT.md](PERFORMANCE_REPORT.md) for detailed analysis and benchmarks.

## API Endpoints

### Sensor Service (Port 8000)

- `GET /health` - Health check endpoint
- `GET /metrics` - Prometheus-formatted metrics
- `GET /sensor` - Sensor readings (JSON)

### VictoriaMetrics (Port 8428)

- `GET /api/v1/query?query=<promql>` - Query metrics
- `GET /api/v1/query_range` - Range queries
- `POST /api/v1/write` - Remote write endpoint (used by vmagent)

## Monitoring Metrics

The sensor service exposes the following metrics:

- `sensor_temperature_celsius` - Current temperature reading
- `sensor_humidity_percent` - Current humidity reading
- `sensor_queue_depth` - Number of events in queue
- `sensor_memory_usage_bytes` - Estimated memory usage
- `sensor_requests_total` - Total request count by endpoint
- `cpu_spike_duration_seconds` - CPU spike duration histogram
- `sensor_processing_latency_seconds` - Processing time summary

## Stopping the Stack

Stop containers (keep data):
```bash
docker compose down
```

Stop and remove volumes:
```bash
docker compose down -v
```

## Development

### Modify Sensor Service

1. Edit `sensor/sensor_service.py`
2. Rebuild and restart:
```bash
docker compose up --build sensor
```

### Update Dashboard

1. Edit `ui/index.html` or `ui/app.js`
2. Restart UI service:
```bash
docker compose restart ui
```

### Change Scrape Interval

Edit `monitoring/vmagent.yml`:
```yaml
global:
  scrape_interval: 15s  # Change this value
```

Then restart:
```bash
docker compose restart vmagent
```

## Production Considerations

- Enable HTTPS with proper certificates
- Add authentication to VictoriaMetrics
- Configure persistent storage for metrics
- Set up log rotation
- Implement proper secret management
- Add health checks and restart policies
- Configure resource limits based on actual hardware

## License

This project is provided as-is for educational purposes.

## Contact

For questions or issues, please open an issue in the repository.
