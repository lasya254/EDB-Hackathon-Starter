# tools/credit_cards.py
"""
Phase 2 — Debt Agent tools (credit card side).

Table used:
    credit_cards(card_id, customer_id, card_name, issuer,
                 credit_limit, current_outstanding, minimum_due,
                 payment_due_date, interest_rate, status)
"""

from google.adk.tools import FunctionTool

from ._bq_helpers import BQ_PREFIX, _run_query, _str_param


# ─────────────────────────────────────────────────────────────────
# Tool — get_credit_cards
# ─────────────────────────────────────────────────────────────────

def get_credit_cards(customer_id: str) -> dict:
    """
    Returns all active credit cards with utilization and due-date alerts.

    Args:
        customer_id: Unique customer identifier.

    Returns:
        dict:
            customer_id  str
            cards        list[{card_id, card_name, issuer,
                                credit_limit, current_outstanding,
                                utilization_pct, minimum_due,
                                payment_due_date, days_to_due,
                                interest_rate}]
            summary      {total_limit, total_outstanding,
                          overall_utilization_pct, card_count}
            alerts       list[{type, card, value, message}]
                           types: high_utilization | payment_due_soon
    """
    rows = _run_query(
        f"""
        SELECT
            card_id,
            card_name,
            issuer,
            credit_limit,
            current_outstanding,
            ROUND(
                current_outstanding / NULLIF(credit_limit, 0) * 100, 2
            ) AS utilization_pct,
            minimum_due,
            payment_due_date,
            DATE_DIFF(
                PARSE_DATE('%Y-%m-%d', payment_due_date),
                CURRENT_DATE(),
                DAY
            ) AS days_to_due,
            interest_rate,
            status
        FROM `{BQ_PREFIX}.credit_cards`
        WHERE customer_id = @customer_id
          AND status = 'active'
        ORDER BY current_outstanding DESC
        """,
        [_str_param("customer_id", customer_id)],
    )

    if not rows:
        return {
            "customer_id": customer_id,
            "cards": [],
            "summary": {
                "total_limit":             0.0,
                "total_outstanding":       0.0,
                "overall_utilization_pct": 0.0,
                "card_count":              0,
            },
            "alerts": [],
        }

    total_limit       = round(sum(r.get("credit_limit")        or 0.0 for r in rows), 2)
    total_outstanding = round(sum(r.get("current_outstanding") or 0.0 for r in rows), 2)
    overall_util      = round(
        total_outstanding / total_limit * 100, 2
    ) if total_limit else 0.0

    # Build alerts
    alerts = []
    for r in rows:
        util = r.get("utilization_pct") or 0.0
        days = r.get("days_to_due")

        if util > 30:
            alerts.append({
                "type":    "high_utilization",
                "card":    r["card_name"],
                "value":   f"{util}%",
                "message": (
                    f"Utilization at {util}% — above 30% threshold. "
                    "Negatively impacts credit score."
                ),
            })

        if days is not None and 0 <= days <= 7:
            alerts.append({
                "type":    "payment_due_soon",
                "card":    r["card_name"],
                "value":   f"₹{r['minimum_due']} due in {days} day(s)",
                "message": "Pay at least minimum due to avoid late fee and interest.",
            })

        if days is not None and days < 0:
            alerts.append({
                "type":    "payment_overdue",
                "card":    r["card_name"],
                "value":   f"₹{r['minimum_due']} overdue by {abs(days)} day(s)",
                "message": "Payment overdue — late charges and credit score impact likely.",
            })

    return {
        "customer_id": customer_id,
        "cards":       rows,
        "summary": {
            "total_limit":             total_limit,
            "total_outstanding":       total_outstanding,
            "overall_utilization_pct": overall_util,
            "card_count":              len(rows),
        },
        "alerts": alerts,
    }


# ─────────────────────────────────────────────────────────────────
# FunctionTool wrapper
# ─────────────────────────────────────────────────────────────────

get_credit_cards_tool = FunctionTool(func=get_credit_cards)
