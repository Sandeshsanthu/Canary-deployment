from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from model_v1 import predict as v1_predict
from model_v2 import predict as v2_predict
from feature_flag import is_enabled, init_unleash, shutdown_unleash
from metrics import REQUEST_COUNT, PREDICTION_LATENCY
from metrics import router as metrics_router



import time
import uuid

app = FastAPI()
templates = Jinja2Templates(directory="templates")

COOKIE_NAME = "uid"

@app.on_event("startup")
def _startup():
    init_unleash()
    start_http_server(5000)

app.include_router(metrics_router)
@app.on_event("shutdown")
def _shutdown():
    shutdown_unleash()

def _get_or_set_uid(request: Request, response):
    uid = request.cookies.get(COOKIE_NAME)
    if not uid:
        uid = str(uuid.uuid4())
        response.set_cookie(COOKIE_NAME, uid, httponly=True, samesite="lax")
    return uid

def _unleash_context(uid: str) -> dict:
    return {"userId": uid}

def _decide(data: dict, ctx: dict) -> dict:
    start = time.time()

    v1_out = v1_predict(data)
    v2_out = v2_predict(data)

    use_v2 = is_enabled("model_v2_enabled", context=ctx)
    chosen = v2_out if use_v2 else v1_out
    model = "v2" if use_v2 else "v1"

    REQUEST_COUNT.labels(model).inc()
    PREDICTION_LATENCY.labels(model).observe(time.time() - start)

    return {
        "model": model,
        "chosen": chosen,
        "shadow": v1_out if model == "v2" else v2_out,
    }

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    response = templates.TemplateResponse("index.html", {"request": request})
    _get_or_set_uid(request, response)
    return response

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

    response = templates.TemplateResponse("result.html", {"request": request, "data": data, "result": None})
    uid = _get_or_set_uid(request, response)
    result = _decide(data, _unleash_context(uid))

    response.context["result"] = result
    return response

@app.post("/predict")
def predict(request: Request, data: dict):
    start = time.time()

    v1_result = v1_predict(data)
    v2_result = v2_predict(data)

    response = JSONResponse(content={})
    uid = _get_or_set_uid(request, response)
    ctx = _unleash_context(uid)

    if is_enabled("model_v2_enabled", context=ctx):
        REQUEST_COUNT.labels("v2").inc()
        PREDICTION_LATENCY.labels("v2").observe(time.time() - start)
        response.body = JSONResponse(content={"decision": v2_result, "model": "v2"}).body
        return response

    REQUEST_COUNT.labels("v1").inc()
    PREDICTION_LATENCY.labels("v1").observe(time.time() - start)
    response.body = JSONResponse(content={"decision": v1_result, "model": "v1"}).body
    return response
