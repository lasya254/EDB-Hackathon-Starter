# tools/investments.py
"""
Phase 2 — Investment Agent tools.

Table used:
    investments(investment_id, customer_id, asset_type, asset_name,
                invested_amount, current_value, monthly_sip,
                risk_level, category, purchase_date, status)
"""

from google.adk.tools import FunctionTool

from ._bq_helpers import BQ_PREFIX, _run_query, _str_param


# ─────────────────────────────────────────────────────────────────
# Tool 1 — get_investment_portfolio
# ─────────────────────────────────────────────────────────────────

def get_investment_portfolio(customer_id: str) -> dict:
    """
    Returns the full active investment portfolio for a customer
    including per-asset returns and a portfolio-level summary.

    Args:
        customer_id: Unique customer identifier.

    Returns:
        dict:
            customer_id           str
            investments           list[{investment_id, asset_type,
                                        asset_name, invested_amount,
                                        current_value, absolute_return,
                                        return_pct, monthly_sip,
                                        risk_level, category,
                                        purchase_date}]
            summary               {total_invested, total_current_value,
                                    total_absolute_return,
                                    total_return_pct,
                                    monthly_sip_total,
                                    investment_count}
            category_allocation_pct  {category: pct}
    """
    rows = _run_query(
        f"""
        SELECT
            investment_id,
            asset_type,
            asset_name,
            invested_amount,
            current_value,
            ROUND(current_value - invested_amount, 2)
                AS absolute_return,
            ROUND(
                (current_value - invested_amount)
                / NULLIF(invested_amount, 0) * 100, 2
            ) AS return_pct,
            monthly_sip,
            risk_level,
            category,
            purchase_date,
            status
        FROM `{BQ_PREFIX}.investments`
        WHERE customer_id = @customer_id
          AND status = 'active'
        ORDER BY current_value DESC
        """,
        [_str_param("customer_id", customer_id)],
    )

    if not rows:
        return {
            "error": f"No active investments found for customer '{customer_id}'.",
            "customer_id": customer_id,
        }

    total_invested = round(sum(r.get("invested_amount") or 0.0 for r in rows), 2)
    total_value    = round(sum(r.get("current_value")   or 0.0 for r in rows), 2)
    total_sip      = round(sum(r.get("monthly_sip")     or 0.0 for r in rows), 2)
    total_return   = round(
        (total_value - total_invested) / total_invested * 100, 2
    ) if total_invested else 0.0

    # Category allocation percentages
    by_cat: dict[str, float] = {}
    for r in rows:
        cat = r.get("category") or "other"
        by_cat[cat] = round(by_cat.get(cat, 0.0) + (r.get("current_value") or 0.0), 2)

    allocation_pct = {
        cat: round(val / total_value * 100, 2) if total_value else 0.0
        for cat, val in by_cat.items()
    }

    return {
        "customer_id": customer_id,
        "investments": rows,
        "summary": {
            "total_invested":        total_invested,
            "total_current_value":   total_value,
            "total_absolute_return": round(total_value - total_invested, 2),
            "total_return_pct":      total_return,
            "monthly_sip_total":     total_sip,
            "investment_count":      len(rows),
        },
        "category_allocation_pct": allocation_pct,
    }


# ─────────────────────────────────────────────────────────────────
# Tool 2 — get_asset_allocation
# ─────────────────────────────────────────────────────────────────

def get_asset_allocation(customer_id: str) -> dict:
    """
    Returns portfolio breakdown by category and risk level
    with allocation percentages and ideal benchmark comparison.

    Args:
        customer_id: Unique customer identifier.

    Returns:
        dict:
            customer_id            str
            total_portfolio_value  float
            by_category            {category: total_value}
            by_category_pct        {category: pct}
            by_risk_pct            {risk_level: pct}
            detailed_rows          list[{category, risk_level, count,
                                          total_invested, total_value,
                                          total_sip, allocation_pct}]
            benchmarks             {conservative, moderate, aggressive}
    """
    rows = _run_query(
        f"""
        SELECT
            category,
            risk_level,
            COUNT(*)                        AS count,
            ROUND(SUM(invested_amount), 2)  AS total_invested,
            ROUND(SUM(current_value),   2)  AS total_value,
            ROUND(SUM(monthly_sip),     2)  AS total_sip
        FROM `{BQ_PREFIX}.investments`
        WHERE customer_id = @customer_id
          AND status = 'active'
        GROUP BY category, risk_level
        ORDER BY total_value DESC
        """,
        [_str_param("customer_id", customer_id)],
    )

    if not rows:
        return {
            "error": f"No active investments found for customer '{customer_id}'.",
            "customer_id": customer_id,
        }

    total_value = sum(r.get("total_value") or 0.0 for r in rows)

    for r in rows:
        r["allocation_pct"] = round(
            (r.get("total_value") or 0.0) / total_value * 100, 2
        ) if total_value else 0.0

    by_cat:  dict[str, float] = {}
    by_risk: dict[str, float] = {}
    for r in rows:
        cat  = r.get("category")   or "other"
        risk = r.get("risk_level") or "unknown"
        by_cat[cat]   = round(by_cat.get(cat, 0.0)   + (r.get("total_value") or 0.0), 2)
        by_risk[risk] = round(by_risk.get(risk, 0.0) + (r.get("total_value") or 0.0), 2)

    to_pct = lambda d: {
        k: round(v / total_value * 100, 2) if total_value else 0.0
        for k, v in d.items()
    }

    return {
        "customer_id":           customer_id,
        "total_portfolio_value": round(total_value, 2),
        "by_category":           by_cat,
        "by_category_pct":       to_pct(by_cat),
        "by_risk_pct":           to_pct(by_risk),
        "detailed_rows":         rows,
        "benchmarks": {
            "conservative": {"equity": 20, "debt": 60, "gold": 10, "cash": 10},
            "moderate":     {"equity": 50, "debt": 35, "gold": 10, "cash":  5},
            "aggressive":   {"equity": 75, "debt": 15, "gold":  5, "cash":  5},
        },
    }


# ─────────────────────────────────────────────────────────────────
# FunctionTool wrappers
# ─────────────────────────────────────────────────────────────────

get_portfolio_tool  = FunctionTool(func=get_investment_portfolio)
get_allocation_tool = FunctionTool(func=get_asset_allocation)
