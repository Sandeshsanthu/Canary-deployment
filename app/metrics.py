from prometheus_client import Counter, Histogram,generate_latest
from flask import Response

@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype="text/plain")

start_http_server(5000)

