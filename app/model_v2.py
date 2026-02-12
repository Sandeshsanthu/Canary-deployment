from math import exp, pow

def _apr_from_credit_score(credit_score: int) -> float:
    if credit_score >= 760: return 0.055
    if credit_score >= 700: return 0.075
    if credit_score >= 660: return 0.105
    if credit_score >= 620: return 0.140
    return 0.210

def _monthly_payment(principal: float, apr: float, months: int) -> float:
    r = apr / 12.0
    if months <= 0:
        return 0.0
    if r == 0:
        return principal / months
    return principal * (r * pow(1 + r, months)) / (pow(1 + r, months) - 1)

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + exp(-x))

def predict(data: dict) -> dict:
    income = float(data["annual_income"])
    credit = int(data["credit_score"])
    monthly_debt = float(data["monthly_debt_payments"])
    loan_amount = float(data["loan_amount"])
    term = int(data["loan_term_months"])
    employment_years = float(data["employment_years"])
    age = int(data["age"])

    apr = _apr_from_credit_score(credit)
    est_payment = _monthly_payment(loan_amount, apr, term)

    monthly_income = income / 12.0 if income > 0 else 0.0
    dti = (monthly_debt + est_payment) / monthly_income if monthly_income > 0 else 1.0

    # Demo score: higher credit/income/employment helps; high DTI and very young age hurts
    z = (
        -2.2
        + 0.006 * (credit - 650)
        + 0.000015 * (income - 50000)
        + 0.25 * (employment_years - 2)
        - 5.5 * (dti - 0.35)
        - 0.6 * (1 if age < 21 else 0)
        - 0.00002 * loan_amount
    )
    approval_prob = _sigmoid(z)

    reasons = []
    if dti > 0.50:
        reasons.append("High DTI risk.")
    if credit < 600:
        reasons.append("Low credit score risk.")
    if employment_years < 0.5:
        reasons.append("Limited employment history.")

    decision = "APPROVED" if approval_prob >= 0.65 else "REJECTED"
    return {
        "decision": decision,
        "approval_probability": round(approval_prob, 3),
        "reasons": reasons,
        "apr": round(apr * 100, 2),
        "estimated_monthly_payment": round(est_payment, 2),
        "dti": round(dti, 3),
    }
