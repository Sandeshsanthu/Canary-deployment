from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from model_v1 import predict as v1_predict
from model_v2 import predict as v2_predict
from feature_flag import is_enabled, init_unleash, shutdown_unleash
from metrics import REQUEST_COUNT, PREDICTION_LATENCY
from metrics import router as metrics_router



import time

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
def _startup():
    init_unleash()
    start_http_server(5000)

app.include_router(metrics_router)
@app.on_event("shutdown")
def _shutdown():
    shutdown_unleash()

def _decide(data: dict) -> dict:
    start = time.time()

    v1_out = v1_predict(data)
    v2_out = v2_predict(data)

    use_v2 = is_enabled("model_v2_enabled")
    chosen = v2_out if use_v2 else v1_out
    model = "v2" if use_v2 else "v1"

    REQUEST_COUNT.labels(model).inc()
    PREDICTION_LATENCY.labels(model).observe(time.time() - start)

    return {
        "model": model,
        "chosen": chosen,
        "shadow": v1_out if model == "v2" else v2_out,  # for demo comparison
    }

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/check", response_class=HTMLResponse)
async def check(request: Request):
    form = await request.form()
    data = {
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
    start = time.time()
    v1_result = v1_predict(data)
    v2_result = v2_predict(data)

    if is_enabled("model_v2_enabled"):
        REQUEST_COUNT.labels("v2").inc()
        PREDICTION_LATENCY.labels("v2").observe(time.time() - start)
        return {"decision": v2_result, "model": "v2"}

    REQUEST_COUNT.labels("v1").inc()
    PREDICTION_LATENCY.labels("v1").observe(time.time() - start)
    return {"decision": v1_result, "model": "v1"}

