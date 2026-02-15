from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import pow
from typing import Dict, List, Optional, Tuple
import hashlib


@dataclass(frozen=True)
class Offer:
    approved_amount: float
    term_months: int
    apr: float  # as decimal (e.g., 0.119 = 11.9%)
    origination_fee: float
    monthly_payment: float


def _monthly_payment(principal: float, apr: float, months: int) -> float:
    r = apr / 12.0
    if months <= 0:
        return 0.0
    if r == 0:
        return principal / months
    return principal * (r * pow(1 + r, months)) / (pow(1 + r, months) - 1)


def _round_money(x: float) -> float:
    return round(float(x), 2)


def _apr_from_credit_score_v1(credit: int) -> float:
    if credit >= 760: return 0.060
    if credit >= 700: return 0.080
    if credit >= 660: return 0.110
    if credit >= 620: return 0.150
    return 0.220


def _apr_from_credit_score_v2(credit: int) -> float:
    if credit >= 760: return 0.055
    if credit >= 700: return 0.075
    if credit >= 660: return 0.105
    if credit >= 620: return 0.140
    return 0.210


def _risk_grade(credit: int, dti: float) -> str:
    # Simple “grade” for demo narrative
    if credit >= 760 and dti <= 0.35: return "A"
    if credit >= 700 and dti <= 0.40: return "B"
    if credit >= 660 and dti <= 0.43: return "C"
    if credit >= 620 and dti <= 0.45: return "D"
    return "E"


def _max_loan_amount(income: float, credit: int) -> float:
    # Soft cap tied to income and credit tier
    base = max(2000.0, min(50000.0, income * 0.8))
    if credit >= 760: return base
    if credit >= 700: return base * 0.90
    if credit >= 660: return base * 0.75
    if credit >= 620: return base * 0.60
    return base * 0.40


def _adverse_action_reasons(reasons: List[str]) -> List[str]:
    # Friendly ECOA-style “top reasons” list for demo
    mapped = []
    for r in reasons:
        if "DTI" in r: mapped.append("High debt-to-income ratio")
        elif "Credit score" in r: mapped.append("Credit score below policy threshold")
        elif "income" in r.lower(): mapped.append("Insufficient income for requested credit")
        elif "Employment" in r: mapped.append("Insufficient employment history")
        elif "Loan amount" in r: mapped.append("Requested amount exceeds policy limits")
        else: mapped.append(r)
    # de-dupe while preserving order
    out = []
    for x in mapped:
        if x not in out:
            out.append(x)
    return out[:4]


def _manual_review_needed(data: Dict) -> bool:
    # Deterministic “refer” trigger for demo (no randomness)
    # Example: large amount + young applicant -> manual review
    amount = float(data["loan_amount"])
    age = int(data["age"])
    credit = int(data["credit_score"])
    return (amount >= 35000 and age < 23) or (credit < 600 and amount >= 15000)


def _decision_id(data: Dict) -> str:
    # deterministic id for demo repeatability
    s = f'{data.get("email","")}|{data.get("loan_amount","")}|{data.get("credit_score","")}|{data.get("annual_income","")}'
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def underwrite(data: Dict, *, version: str) -> Dict:
    """
    Returns:
      - APPROVED: with offer
      - COUNTEROFFER: with smaller offer
      - REFER: manual review
      - REJECTED: with reasons + adverse_action_reasons
    """
    income = float(data["annual_income"])
    credit = int(data["credit_score"])
    monthly_debt = float(data["monthly_debt_payments"])
    loan_amount = float(data["loan_amount"])
    term = int(data["loan_term_months"])
    employment_years = float(data["employment_years"])
    age = int(data["age"])
    housing_payment = float(data.get("housing_payment", 0.0))

    reasons: List[str] = []

    # Basic eligibility / compliance-ish checks (demo only)
    if age < 18:
        reasons.append("Applicant must be 18+.")
    if employment_years < 0:
        reasons.append("Employment years must be non-negative.")
    if income <= 0:
        reasons.append("Annual income must be positive.")
    if loan_amount <= 0 or term <= 0:
        reasons.append("Loan amount/term must be positive.")
    if credit < 300 or credit > 850:
        reasons.append("Credit score must be between 300 and 850.")

    # Policy thresholds
    if employment_years < 1:
        reasons.append("Employment length must be >= 1 year.")
    if credit < 580:
        reasons.append("Credit score below minimum (580).")
    if income < 25000:
        reasons.append("Annual income below minimum ($25,000).")

    max_amt = _max_loan_amount(income, credit)
    if loan_amount > max_amt:
        reasons.append(f"Loan amount exceeds max allowed (${_round_money(max_amt)}).")

    # Compute affordability
    apr_fn = _apr_from_credit_score_v2 if version == "v2" else _apr_from_credit_score_v1
    apr = apr_fn(credit)
    est_payment = _monthly_payment(loan_amount, apr, term)

    monthly_income = income / 12.0
    # include housing payment to feel “real”
    total_monthly_obligations = monthly_debt + housing_payment + est_payment
    dti = total_monthly_obligations / monthly_income if monthly_income > 0 else 1.0

    if dti > 0.45:
        reasons.append(f"DTI too high ({dti:.2f} > 0.45).")

    # Add manual review path
    if not reasons and _manual_review_needed(data):
        return {
            "decision_id": _decision_id(data),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "model_version": version,
            "decision": "REFER",
            "risk_grade": _risk_grade(credit, dti),
            "dti": round(dti, 3),
            "reasons": ["Application requires manual review."],
            "offer": None,
        }

    # Hard reject if policy failed
    if reasons:
        return {
            "decision_id": _decision_id(data),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "model_version": version,
            "decision": "REJECTED",
            "risk_grade": _risk_grade(credit, dti),
            "dti": round(dti, 3),
            "reasons": reasons,
            "adverse_action_reasons": _adverse_action_reasons(reasons),
            "pricing": {
                "apr_percent": round(apr * 100, 2),
                "estimated_monthly_payment": _round_money(est_payment),
            },
            "offer": None,
        }

    # Otherwise approve or counter-offer if affordability is tight
    # Tight affordability: PTI (payment-to-income) > 15% -> counter offer smaller amount
    pti = est_payment / monthly_income
    approved_amount = loan_amount
    approved_term = term
    approved_apr = apr

    if pti > 0.15:
        # counter by lowering amount (keep term) to hit ~13% PTI
        target_payment = monthly_income * 0.13
        # back-solve principal via simple search (demo-friendly)
        lo, hi = 1000.0, loan_amount
        for _ in range(30):
            mid = (lo + hi) / 2.0
            p = _monthly_payment(mid, approved_apr, approved_term)
            if p > target_payment:
                hi = mid
            else:
                lo = mid
        approved_amount = _round_money(lo)

    orig_fee = _round_money(max(99.0, min(loan_amount * 0.02, 499.0)))
    final_payment = _monthly_payment(approved_amount, approved_apr, approved_term)

    offer = Offer(
        approved_amount=approved_amount,
        term_months=approved_term,
        apr=approved_apr,
        origination_fee=orig_fee,
        monthly_payment=_round_money(final_payment),
    )

    decision = "APPROVED" if approved_amount == loan_amount else "COUNTEROFFER"

    return {
        "decision_id": _decision_id(data),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model_version": version,
        "decision": decision,
        "risk_grade": _risk_grade(credit, dti),
        "dti": round(dti, 3),
        "reasons": [],
        "pricing": {
            "apr_percent": round(approved_apr * 100, 2),
            "monthly_payment": offer.monthly_payment,
            "origination_fee": offer.origination_fee,
        },
        "offer": {
            "approved_amount": offer.approved_amount,
            "term_months": offer.term_months,
            "apr_percent": round(offer.apr * 100, 2),
            "origination_fee": offer.origination_fee,
            "estimated_monthly_payment": offer.monthly_payment,
        },
    }
