# tools/loans.py
"""
Phase 2 — Debt Agent tools (loan side).

Table used:
    loans(loan_id, customer_id, loan_type, lender_name,
          principal_amount, outstanding_amount, interest_rate,
          emi, tenure_months, remaining_months,
          start_date, end_date, status)
"""

import math

from google.adk.tools import FunctionTool

from ._bq_helpers import BQ_PREFIX, _run_query, _str_param


# ─────────────────────────────────────────────────────────────────
# Tool 1 — get_all_loans
# ─────────────────────────────────────────────────────────────────

def get_all_loans(customer_id: str) -> dict:
    """
    Returns all active loans with monthly interest/principal breakdown.

    Args:
        customer_id: Unique customer identifier.

    Returns:
        dict:
            customer_id  str
            loans        list[{loan_id, loan_type, lender_name,
                                principal_amount, outstanding_amount,
                                interest_rate, emi, tenure_months,
                                remaining_months, monthly_interest,
                                monthly_principal, start_date,
                                end_date}]
            summary      {total_outstanding, total_monthly_emi,
                          loan_count}
    """
    rows = _run_query(
        f"""
        SELECT
            loan_id,
            loan_type,
            lender_name,
            principal_amount,
            outstanding_amount,
            interest_rate,
            emi,
            tenure_months,
            remaining_months,
            start_date,
            end_date,
            ROUND(
                outstanding_amount * interest_rate / 100 / 12, 2
            ) AS monthly_interest,
            ROUND(
                emi - (outstanding_amount * interest_rate / 100 / 12), 2
            ) AS monthly_principal,
            status
        FROM `{BQ_PREFIX}.loans`
        WHERE customer_id = @customer_id
          AND status = 'active'
        ORDER BY interest_rate DESC
        """,
        [_str_param("customer_id", customer_id)],
    )

    if not rows:
        return {
            "customer_id": customer_id,
            "loans": [],
            "summary": {
                "total_outstanding":  0.0,
                "total_monthly_emi":  0.0,
                "loan_count":         0,
            },
        }

    return {
        "customer_id": customer_id,
        "loans": rows,
        "summary": {
            "total_outstanding":  round(sum(r.get("outstanding_amount") or 0.0 for r in rows), 2),
            "total_monthly_emi":  round(sum(r.get("emi")                or 0.0 for r in rows), 2),
            "loan_count":         len(rows),
        },
    }


# ─────────────────────────────────────────────────────────────────
# Tool 2 — get_debt_metrics
# ─────────────────────────────────────────────────────────────────

def get_debt_metrics(customer_id: str, monthly_income: float) -> dict:
    """
    Calculates debt health ratios and optimal repayment strategies.

    Args:
        customer_id:    Unique customer identifier.
        monthly_income: Customer's monthly take-home income in ₹.

    Returns:
        dict:
            customer_id          str
            monthly_income       float
            total_monthly_emi    float
            debt_to_income_pct   float   — EMIs / income × 100
            health_status        str     — healthy|moderate|concerning|critical
            health_score         int     — 0-100
            repayment_strategies {avalanche_order, snowball_order,
                                  recommended, reason}
            loans                list    — full loan rows
    """
    loan_data = get_all_loans(customer_id)
    loans     = loan_data.get("loans", [])
    total_emi = loan_data["summary"]["total_monthly_emi"]

    dti = round(total_emi / monthly_income * 100, 2) if monthly_income else 0.0

    # Health thresholds
    if dti <= 30:
        health, score = "healthy",    90
    elif dti <= 40:
        health, score = "moderate",   70
    elif dti <= 50:
        health, score = "concerning", 50
    else:
        health, score = "critical",   25

    # Repayment strategy orderings
    avalanche = [
        r["loan_id"]
        for r in sorted(loans, key=lambda x: x.get("interest_rate") or 0, reverse=True)
    ]
    snowball = [
        r["loan_id"]
        for r in sorted(loans, key=lambda x: x.get("outstanding_amount") or 0)
    ]

    # Extra-payment impact on highest-rate loan
    extra_payment_analysis = {}
    if avalanche and monthly_income:
        top_loan    = next(l for l in loans if l["loan_id"] == avalanche[0])
        extra       = round(monthly_income * 0.10, 2)   # 10% of income as extra
        annual_save = round(extra * 12 * (top_loan.get("interest_rate") or 0) / 100, 2)
        extra_payment_analysis = {
            "suggested_extra_monthly": extra,
            "target_loan":             top_loan["loan_id"],
            "target_loan_type":        top_loan["loan_type"],
            "estimated_annual_saving": annual_save,
        }

    return {
        "customer_id":        customer_id,
        "monthly_income":     monthly_income,
        "total_monthly_emi":  total_emi,
        "debt_to_income_pct": dti,
        "health_status":      health,
        "health_score":       score,
        "repayment_strategies": {
            "avalanche_order": avalanche,
            "snowball_order":  snowball,
            "recommended":     "avalanche",
            "reason":          "Minimises total interest paid over loan lifetime",
        },
        "extra_payment_analysis": extra_payment_analysis,
        "loans": loans,
    }


# ─────────────────────────────────────────────────────────────────
# FunctionTool wrappers
# ─────────────────────────────────────────────────────────────────

get_loans_tool        = FunctionTool(func=get_all_loans)
get_debt_metrics_tool = FunctionTool(func=get_debt_metrics)
