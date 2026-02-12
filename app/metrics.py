from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "prediction_requests_total",
    "Total prediction requests",
    ["model"]
)

PREDICTION_LATENCY = Histogram(
    "prediction_latency_seconds",
    "Prediction latency",
    ["model"]
)

