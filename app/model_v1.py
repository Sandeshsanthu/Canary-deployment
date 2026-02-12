from math import pow

def _apr_from_credit_score(credit_score: int) -> float:
    # demo mapping only
    if credit_score >= 760: return 0.060
    if credit_score >= 700: return 0.080
    if credit_score >= 660: return 0.110
    if credit_score >= 620: return 0.150
    return 0.220

def _monthly_payment(principal: float, apr: float, months: int) -> float:
    r = apr / 12.0
    if months <= 0:
        return 0.0
    if r == 0:
        return principal / months
    return principal * (r * pow(1 + r, months)) / (pow(1 + r, months) - 1)

def predict(data: dict) -> dict:
    income = float(data["annual_income"])
    credit = int(data["credit_score"])
    monthly_debt = float(data["monthly_debt_payments"])
    loan_amount = float(data["loan_amount"])
    term = int(data["loan_term_months"])
    employment_years = float(data["employment_years"])
    age = int(data["age"])

    reasons = []
    if age < 18:
        reasons.append("Applicant must be 18+.")
    if employment_years < 1:
        reasons.append("Employment length must be >= 1 year.")
    if credit < 620:
        reasons.append("Credit score below minimum (620).")
    if income < 30000:
        reasons.append("Annual income below minimum ($30,000).")
    if loan_amount <= 0 or term <= 0:
        reasons.append("Loan amount/term must be positive.")

    apr = _apr_from_credit_score(credit)
    est_payment = _monthly_payment(loan_amount, apr, term)

    monthly_income = income / 12.0 if income > 0 else 0.0
    dti = (monthly_debt + est_payment) / monthly_income if monthly_income > 0 else 1.0

    if dti > 0.43:
        reasons.append(f"DTI too high ({dti:.2f} > 0.43).")
    if loan_amount > income * 1.5:
        reasons.append("Requested loan too high vs income.")

    decision = "APPROVED" if len(reasons) == 0 else "REJECTED"
    return {
        "decision": decision,
        "reasons": reasons,
        "apr": round(apr * 100, 2),
        "estimated_monthly_payment": round(est_payment, 2),
        "dti": round(dti, 3),
    }
