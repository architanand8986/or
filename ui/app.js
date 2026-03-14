const VM_API = "/api/v1";
const REFRESH_INTERVAL = 10_000;
const MAX_POINTS = 60;

const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 300 },
    scales: {
        x: { ticks: { color: "#8b949e", maxTicksLimit: 10 }, grid: { color: "#21262d" } },
        y: { ticks: { color: "#8b949e" }, grid: { color: "#21262d" } },
    },
    plugins: { legend: { display: false } },
};

function makeChart(canvasId, label, borderColor) {
    const ctx = document.getElementById(canvasId).getContext("2d");
    return new Chart(ctx, {
        type: "line",
        data: {
            labels: [],
            datasets: [{
                label,
                data: [],
                borderColor,
                backgroundColor: borderColor + "22",
                fill: true,
                tension: 0.3,
                pointRadius: 2,
            }],
        },
        options: chartDefaults,
    });
}

const tempChart  = makeChart("tempChart",  "Temperature (°C)", "#58a6ff");
const queueChart = makeChart("queueChart", "Queue Depth",      "#d29922");
const cpuChart   = makeChart("cpuChart",   "CPU Spike (s)",    "#f85149");

function timeLabel() {
    return new Date().toLocaleTimeString();
}

function pushPoint(chart, label, value) {
    chart.data.labels.push(label);
    chart.data.datasets[0].data.push(value);
    if (chart.data.labels.length > MAX_POINTS) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }
    chart.update("none");
}

async function queryInstant(promql) {
    try {
        const url = `${VM_API}/query?query=${encodeURIComponent(promql)}`;
        const resp = await fetch(url);
        const json = await resp.json();
        if (json.status === "success" && json.data.result.length > 0) {
            return parseFloat(json.data.result[0].value[1]);
        }
    } catch (e) {
        console.warn("Query failed:", promql, e);
    }
    return null;
}

function setEl(id, text, cls) {
    const el = document.getElementById(id);
    el.textContent = text;
    el.className = "value" + (cls ? ` ${cls}` : "");
}

async function poll() {
    const now = timeLabel();
    try {
        const [temp, hum, queue, reqs, cpuAvg, mem] = await Promise.all([
            queryInstant("sensor_temperature_celsius"),
            queryInstant("sensor_humidity_percent"),
            queryInstant("sensor_queue_depth"),
            queryInstant('sum(sensor_requests_total)'),
            queryInstant("rate(cpu_spike_duration_seconds_sum[1m]) / rate(cpu_spike_duration_seconds_count[1m])"),
            queryInstant("sensor_memory_usage_bytes"),
        ]);

        if (temp !== null)  { setEl("temperature", temp.toFixed(1) + " °C", temp > 30 ? "warn" : "ok"); pushPoint(tempChart, now, temp); }
        if (hum !== null)   { setEl("humidity", hum.toFixed(1) + " %", "ok"); }
        if (queue !== null) { setEl("queue-depth", Math.round(queue), queue > 800 ? "warn" : "ok"); pushPoint(queueChart, now, queue); }
        if (reqs !== null)  { setEl("request-count", Math.round(reqs), "ok"); }
        if (cpuAvg !== null){ setEl("cpu-spike", cpuAvg.toFixed(4) + " s", cpuAvg > 0.1 ? "warn" : "ok"); pushPoint(cpuChart, now, cpuAvg); }
        if (mem !== null)   { setEl("memory-usage", (mem / 1024).toFixed(1) + " KB", "ok"); }

        document.getElementById("statusDot").className = "status-dot green";
        document.getElementById("statusText").textContent = "Connected";
    } catch (e) {
        document.getElementById("statusDot").className = "status-dot red";
        document.getElementById("statusText").textContent = "Disconnected";
    }
}

poll();
setInterval(poll, REFRESH_INTERVAL);
