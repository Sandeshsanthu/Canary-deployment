from math import exp, pow

DTI_CAP = 0.45
PTI_CAP = 0.18

MIN_LOAN = 1_000
MAX_LOAN = 100_000
MIN_TERM = 12
MAX_TERM = 84


def _apr_from_credit_score(credit_score: int) -> float:
    # Simplified “pricing grid” by credit band (demo)
    if credit_score >= 780:
        return 0.055
    if credit_score >= 740:
        return 0.065
    if credit_score >= 700:
        return 0.079
    if credit_score >= 660:
        return 0.105
    if credit_score >= 620:
        return 0.139
    if credit_score >= 580:
        return 0.179
    return 0.219


def _monthly_payment(principal: float, apr: float, months: int) -> float:
    r = apr / 12.0
    if months <= 0:
        return 0.0
    if r == 0:
        return principal / months
    return principal * (r * pow(1 + r, months)) / (pow(1 + r, months) - 1)


def _principal_from_payment(payment: float, apr: float, months: int) -> float:
    # Inverse of amortization formula
    r = apr / 12.0
    if months <= 0 or payment <= 0:
        return 0.0
    if r == 0:
        return payment * months
    denom = r * pow(1 + r, months)
    if denom == 0:
        return 0.0
    return payment * (pow(1 + r, months) - 1) / denom


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + exp(-x))


def _risk_grade(p: float) -> str:
    if p >= 0.85:
        return "A"
    if p >= 0.75:
        return "B"
    if p >= 0.65:
        return "C"
    if p >= 0.55:
        return "D"
    return "E"


def predict(data: dict) -> dict:
    income = float(data["annual_income"])
    credit = int(data["credit_score"])
    monthly_debt = float(data["monthly_debt_payments"])
    loan_amount = float(data["loan_amount"])
    term = int(data["loan_term_months"])
    employment_years = float(data["employment_years"])
    age = int(data["age"])

    reasons = []

    # (A) Hard stops / basic policy
    if age < 18:
        reasons.append("Applicant must be 18+.")
    if income <= 0:
        reasons.append("Income must be greater than $0.")
    if credit < 560:
        reasons.append("Credit score below minimum (560).")
    if term < MIN_TERM or term > MAX_TERM:
        reasons.append(f"Term must be {MIN_TERM}–{MAX_TERM} months.")
    if loan_amount < MIN_LOAN or loan_amount > MAX_LOAN:
        reasons.append(f"Loan amount must be ${MIN_LOAN:,}–${MAX_LOAN:,}.")

    apr = _apr_from_credit_score(credit)
    est_payment = _monthly_payment(loan_amount, apr, term)

    monthly_income = income / 12.0 if income > 0 else 0.0
    dti = (monthly_debt + est_payment) / monthly_income if monthly_income > 0 else 1.0
    pti = est_payment / monthly_income if monthly_income > 0 else 1.0

    # (B) Affordability caps -> compute max affordable payment
    max_by_pti = monthly_income * PTI_CAP
    max_by_dti = (monthly_income * DTI_CAP) - monthly_debt
    max_affordable_payment = max(0.0, min(max_by_pti, max_by_dti))

    max_affordable_loan = _principal_from_payment(max_affordable_payment, apr, term)

    # If hard-stop failed, decline immediately
    if reasons:
        return {
            "decision": "REJECTED",
            "risk_grade": "E",
            "approval_probability": 0.0,
            "reasons": reasons,
            "apr": round(apr * 100, 2),
            "estimated_monthly_payment": round(est_payment, 2),
            "dti": round(dti, 3),
            "pti": round(pti, 3),
        }

    # (D) Risk score (demo scorecard-style)
    z = (
        -1.9
        + 0.007 * (credit - 650)
        + 0.000012 * (income - 50_000)
        + 0.22 * (employment_years - 2)
        - 6.0 * (dti - 0.35)
        - 2.8 * (pti - 0.16)
        - 0.5 * (1 if age < 21 else 0)
        - 0.000018 * loan_amount
    )
    approval_prob = _sigmoid(z)
    grade = _risk_grade(approval_prob)

    # Add soft reasons (explainability-lite)
    if dti > DTI_CAP:
        reasons.append("DTI exceeds affordability cap.")
    if pti > PTI_CAP:
        reasons.append("Payment-to-income exceeds affordability cap.")
    if employment_years < 0.5:
        reasons.append("Limited employment history.")
    if credit < 620:
        reasons.append("Subprime credit band (higher risk).")

    counteroffer = None

    # (C) Counteroffer if amount exceeds affordability
    if max_affordable_loan > 0 and loan_amount > max_affordable_loan * 1.02:
        counteroffer = max_affordable_loan

    # Final decision bands
    if counteroffer is not None:
        decision = "MANUAL_REVIEW"
        reasons.append("Requested amount exceeds max affordable loan.")
    else:
        if approval_prob >= 0.75 and dti <= DTI_CAP and pti <= PTI_CAP:
            decision = "APPROVED"
        elif approval_prob >= 0.60:
            decision = "MANUAL_REVIEW"
        else:
            decision = "REJECTED"

    out = {
        "decision": decision,
        "risk_grade": grade,
        "approval_probability": round(approval_prob, 3),
        "reasons": reasons,
        "apr": round(apr * 100, 2),
        "estimated_monthly_payment": round(est_payment, 2),
        "dti": round(dti, 3),
        "pti": round(pti, 3),
        "max_affordable_loan": round(max_affordable_loan, 0),
    }
    if counteroffer is not None:
        out["counteroffer_loan_amount"] = round(counteroffer, 0)

    return out
