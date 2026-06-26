# tools/fixed_deposits.py
"""
Phase 2 — FD Agent tools.

Table used:
    fixed_deposits(fd_id, customer_id, bank_name,
                   principal_amount, interest_rate, maturity_amount,
                   start_date, maturity_date, tenure_months, status)
"""

from google.adk.tools import FunctionTool

from ._bq_helpers import BQ_PREFIX, _run_query, _str_param


# ─────────────────────────────────────────────────────────────────
# Tool — get_fixed_deposits
# ─────────────────────────────────────────────────────────────────

def get_fixed_deposits(customer_id: str) -> dict:
    """
    Returns all active fixed deposits with maturity details and
    upcoming maturity alerts (within 90 days).

    Args:
        customer_id: Unique customer identifier.

    Returns:
        dict:
            customer_id          str
            fds                  list[{fd_id, bank_name,
                                        principal_amount, interest_rate,
                                        maturity_amount, expected_interest,
                                        start_date, maturity_date,
                                        days_to_maturity, tenure_months}]
            summary              {total_principal, total_maturity_value,
                                   total_expected_interest, fd_count}
            upcoming_maturities  list  — FDs maturing in ≤ 90 days
            maturity_alerts      list[{type, fd_id, bank, message}]
    """
    rows = _run_query(
        f"""
        SELECT
            fd_id,
            bank_name,
            principal_amount,
            interest_rate,
            maturity_amount,
            ROUND(maturity_amount - principal_amount, 2) AS expected_interest,
            start_date,
            maturity_date,
            DATE_DIFF(
                PARSE_DATE('%Y-%m-%d', maturity_date),
                CURRENT_DATE(),
                DAY
            ) AS days_to_maturity,
            tenure_months,
            status
        FROM `{BQ_PREFIX}.fixed_deposits`
        WHERE customer_id = @customer_id
          AND status = 'active'
        ORDER BY maturity_date ASC
        """,
        [_str_param("customer_id", customer_id)],
    )

    if not rows:
        return {
            "customer_id": customer_id,
            "fds": [],
            "summary": {
                "total_principal":         0.0,
                "total_maturity_value":    0.0,
                "total_expected_interest": 0.0,
                "fd_count":                0,
            },
            "upcoming_maturities": [],
            "maturity_alerts":     [],
        }

    total_principal = round(sum(r.get("principal_amount")  or 0.0 for r in rows), 2)
    total_maturity  = round(sum(r.get("maturity_amount")   or 0.0 for r in rows), 2)
    total_interest  = round(total_maturity - total_principal, 2)

    upcoming = [
        r for r in rows
        if 0 <= (r.get("days_to_maturity") or 9999) <= 90
    ]

    alerts = []
    for r in upcoming:
        days = r.get("days_to_maturity")
        alerts.append({
            "type":    "maturing_soon",
            "fd_id":   r["fd_id"],
            "bank":    r["bank_name"],
            "message": (
                f"FD of ₹{r['principal_amount']:,.0f} at {r['bank_name']} "
                f"matures in {days} day(s) on {r['maturity_date']}. "
                f"Maturity value: ₹{r['maturity_amount']:,.0f}. "
                "Consider renewal or reinvestment."
            ),
        })

    return {
        "customer_id":        customer_id,
        "fds":                rows,
        "summary": {
            "total_principal":         total_principal,
            "total_maturity_value":    total_maturity,
            "total_expected_interest": total_interest,
            "fd_count":                len(rows),
        },
        "upcoming_maturities": upcoming,
        "maturity_alerts":     alerts,
    }


# ─────────────────────────────────────────────────────────────────
# FunctionTool wrapper
# ─────────────────────────────────────────────────────────────────

get_fds_tool = FunctionTool(func=get_fixed_deposits)
