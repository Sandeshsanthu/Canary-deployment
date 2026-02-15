from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from prometheus_client import start_http_server, Counter, Histogram
import time

from feature_flag import is_enabled, init_unleash, shutdown_unleash
from underwriting import underwrite

app = FastAPI()
templates = Jinja2Templates(directory="templates")

REQUEST_COUNT = Counter("loan_decisions_total", "Count of loan decisions", ["model_version", "decision"])
DECISION_LATENCY = Histogram("loan_decision_latency_seconds", "Decision latency", ["model_version"])


@app.on_event("startup")
def _startup():
    init_unleash()
    # Expose Prometheus on port 5000 (/metrics) to match your Service/annotations
    start_http_server(5000)


@app.on_event("shutdown")
def _shutdown():
    shutdown_unleash()


def _decide(data: dict) -> dict:
    start = time.time()

    v1_out = underwrite(data, version="v1")
    v2_out = underwrite(data, version="v2")

    use_v2 = is_enabled("model_v2_enabled")
    chosen = v2_out if use_v2 else v1_out
    shadow = v1_out if use_v2 else v2_out

    model = "v2" if use_v2 else "v1"

    REQUEST_COUNT.labels(model, chosen["decision"]).inc()
    DECISION_LATENCY.labels(model).observe(time.time() - start)

    return {"model": model, "chosen": chosen, "shadow": shadow}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/check", response_class=HTMLResponse)
async def check(request: Request):
    form = await request.form()
    data = {
        # “Real” app fields (still demo)
        "full_name": str(form.get("full_name", "")),
        "email": str(form.get("email", "")),
        "phone": str(form.get("phone", "")),
        "state": str(form.get("state", "")),
        "loan_purpose": str(form.get("loan_purpose", "")),
        "housing_payment": float(form.get("housing_payment", 0) or 0),

        # underwriting inputs
        "annual_income": float(form["annual_income"]),
        "credit_score": int(form["credit_score"]),
        "monthly_debt_payments": float(form["monthly_debt_payments"]),
        "loan_amount": float(form["loan_amount"]),
        "loan_term_months": int(form["loan_term_months"]),
        "employment_years": float(form["employment_years"]),
        "age": int(form["age"]),
    }
    result = _decide(data)
    return templates.TemplateResponse("result.html", {"request": request, "data": data, "result": result})


@app.post("/predict")
def predict(data: dict):
    # API version of the same logic
    result = _decide(data)
    return {"model": result["model"], "decision": result["chosen"], "shadow": result["shadow"]}
