# tools/insurance.py
"""
Phase 2 — Insurance Agent tools.

Table used:
    insurance(policy_id, customer_id, policy_type, policy_name,
              insurer, sum_assured, premium, frequency,
              start_date, end_date, nominee, status)
"""

from google.adk.tools import FunctionTool

from ._bq_helpers import BQ_PREFIX, _run_query, _str_param


# ─────────────────────────────────────────────────────────────────
# Helper — normalise premium to annual
# ─────────────────────────────────────────────────────────────────

def _annual_premium(premium: float, frequency: str) -> float:
    freq = (frequency or "annual").lower()
    if freq == "monthly":
        return premium * 12
    if freq == "quarterly":
        return premium * 4
    return premium   # annual


# ─────────────────────────────────────────────────────────────────
# Tool 1 — get_insurance_policies
# ─────────────────────────────────────────────────────────────────

def get_insurance_policies(customer_id: str) -> dict:
    """
    Returns all active insurance policies grouped by type,
    with annual premium total and expiry alerts.

    Args:
        customer_id: Unique customer identifier.

    Returns:
        dict:
            customer_id         str
            policies            list[{policy_id, policy_type,
                                       policy_name, insurer,
                                       sum_assured, premium,
                                       frequency, annual_premium,
                                       start_date, end_date,
                                       days_to_expiry, nominee}]
            by_type             {policy_type: list[policy]}
            summary             {annual_premium_total, policy_count}
            expiring_soon       list  — policies expiring in ≤ 60 days
            expiry_alerts       list[{type, policy_id, policy_name,
                                       message}]
    """
    rows = _run_query(
        f"""
        SELECT
            policy_id,
            policy_type,
            policy_name,
            insurer,
            sum_assured,
            premium,
            frequency,
            start_date,
            end_date,
            DATE_DIFF(
                PARSE_DATE('%Y-%m-%d', end_date),
                CURRENT_DATE(),
                DAY
            ) AS days_to_expiry,
            nominee,
            status
        FROM `{BQ_PREFIX}.insurance`
        WHERE customer_id = @customer_id
          AND status = 'active'
        ORDER BY policy_type, sum_assured DESC
        """,
        [_str_param("customer_id", customer_id)],
    )

    if not rows:
        return {
            "customer_id":  customer_id,
            "policies":     [],
            "by_type":      {},
            "summary":      {"annual_premium_total": 0.0, "policy_count": 0},
            "expiring_soon": [],
            "expiry_alerts": [],
        }

    # Enrich with annual_premium field
    for r in rows:
        r["annual_premium"] = round(
            _annual_premium(r.get("premium") or 0.0, r.get("frequency") or "annual"), 2
        )

    annual_total = round(sum(r["annual_premium"] for r in rows), 2)

    # Group by type
    by_type: dict[str, list] = {}
    for r in rows:
        pt = r.get("policy_type") or "other"
        by_type.setdefault(pt, []).append(r)

    # Expiry within 60 days
    expiring = [
        r for r in rows
        if 0 <= (r.get("days_to_expiry") or 9999) <= 60
    ]

    alerts = []
    for r in expiring:
        days = r.get("days_to_expiry")
        alerts.append({
            "type":        "expiring_soon",
            "policy_id":   r["policy_id"],
            "policy_name": r["policy_name"],
            "message": (
                f"{r['policy_type'].replace('_', ' ').title()} policy "
                f"'{r['policy_name']}' from {r['insurer']} expires "
                f"in {days} day(s) on {r['end_date']}. "
                "Renew promptly to avoid coverage lapse."
            ),
        })

    return {
        "customer_id":   customer_id,
        "policies":      rows,
        "by_type":       by_type,
        "summary": {
            "annual_premium_total": annual_total,
            "policy_count":         len(rows),
        },
        "expiring_soon": expiring,
        "expiry_alerts": alerts,
    }


# ─────────────────────────────────────────────────────────────────
# Tool 2 — check_insurance_adequacy
# ─────────────────────────────────────────────────────────────────

def check_insurance_adequacy(
    customer_id:       str,
    annual_income:     float,
    total_liabilities: float,
    dependents:        int,
    age:               int,
) -> dict:
    """
    Analyses whether life and health insurance cover is adequate
    for the customer's profile.

    Life cover formula:
        (annual_income × working_years_left × 0.7)
        + total_liabilities
        + (₹10,00,000 × dependents)

    Health cover benchmark:
        Age < 40 → ₹10,00,000 per person
        Age ≥ 40 → ₹15,00,000 per person

    Args:
        customer_id:        Unique customer identifier.
        annual_income:      Annual gross income in ₹.
        total_liabilities:  Total outstanding debt in ₹.
        dependents:         Number of financial dependents.
        age:                Customer's current age in years.

    Returns:
        dict:
            customer_id       str
            life_adequacy     {current_cover, required_cover, gap,
                                coverage_ratio, status, policies}
            health_adequacy   {current_cover, required_cover, gap,
                                coverage_ratio, status, policies}
            annual_premium    float  — total annual insurance spend
            overall_status    str    — adequate|moderate|inadequate
    """
    data    = get_insurance_policies(customer_id)
    by_type = data.get("by_type", {})

    # ── Life cover ────────────────────────────────────────────────
    life_policies  = by_type.get("term_life", []) + by_type.get("life", [])
    current_life   = round(sum(p.get("sum_assured") or 0.0 for p in life_policies), 0)

    working_years  = max(0, 60 - age)
    required_life  = round(
        (annual_income * working_years * 0.7)
        + total_liabilities
        + (dependents * 1_000_000),
        0,
    )
    life_gap   = round(max(0.0, required_life - current_life), 0)
    life_ratio = round(current_life / required_life * 100, 1) if required_life else 100.0

    life_status = (
        "adequate"   if life_ratio >= 100 else
        "moderate"   if life_ratio >= 70  else
        "inadequate"
    )

    # ── Health cover ─────────────────────────────────────────────
    health_policies  = by_type.get("health", [])
    current_health   = round(sum(p.get("sum_assured") or 0.0 for p in health_policies), 0)
    required_health  = 1_500_000 if age >= 40 else 1_000_000  # per-person tier-1 benchmark

    health_gap   = round(max(0.0, required_health - current_health), 0)
    health_ratio = round(current_health / required_health * 100, 1) if required_health else 100.0

    health_status = (
        "adequate"   if health_ratio >= 100 else
        "moderate"   if health_ratio >= 60  else
        "inadequate"
    )

    # ── Overall status ────────────────────────────────────────────
    statuses = [life_status, health_status]
    if all(s == "adequate" for s in statuses):
        overall = "adequate"
    elif "inadequate" in statuses:
        overall = "inadequate"
    else:
        overall = "moderate"

    return {
        "customer_id": customer_id,
        "life_adequacy": {
            "current_cover":  current_life,
            "required_cover": required_life,
            "gap":            life_gap,
            "coverage_ratio": life_ratio,
            "status":         life_status,
            "policies":       life_policies,
        },
        "health_adequacy": {
            "current_cover":  current_health,
            "required_cover": required_health,
            "gap":            health_gap,
            "coverage_ratio": health_ratio,
            "status":         health_status,
            "policies":       health_policies,
        },
        "annual_premium":  data["summary"]["annual_premium_total"],
        "overall_status":  overall,
    }


# ─────────────────────────────────────────────────────────────────
# FunctionTool wrappers
# ─────────────────────────────────────────────────────────────────

get_policies_tool = FunctionTool(func=get_insurance_policies)
get_adequacy_tool = FunctionTool(func=check_insurance_adequacy)
