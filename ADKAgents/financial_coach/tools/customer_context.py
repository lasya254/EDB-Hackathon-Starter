# tools/customer_context.py
"""
Phase 1 — Customer Context Agent tools.

Tables used:
    accounts(account_id, customer_id, product_type, balance)
    transactions(account_id, description, amount, type, date)
"""

from google.adk.tools import FunctionTool

from ._bq_helpers import BQ_PREFIX, _run_query, _str_param


# ─────────────────────────────────────────────────────────────────
# Tool 1 — get_customer_profile
# ─────────────────────────────────────────────────────────────────

def get_customer_profile(customer_id: str) -> dict:
    """
    Retrieves all bank accounts for a customer with total balance.

    Args:
        customer_id: Unique customer identifier, e.g. "C1001".

    Returns:
        dict:
            customer_id       str
            accounts          list[{account_id, product_type, balance}]
            total_balance     float  — sum of all account balances
            account_count     int
    """
    rows = _run_query(
        f"""
        SELECT
            account_id,
            customer_id,
            product_type,
            balance
        FROM `{BQ_PREFIX}.accounts`
        WHERE customer_id = @customer_id
        ORDER BY balance DESC
        """,
        [_str_param("customer_id", customer_id)],
    )

    if not rows:
        return {
            "error": f"No accounts found for customer '{customer_id}'.",
            "customer_id": customer_id,
        }

    total = round(sum(r.get("balance") or 0.0 for r in rows), 2)

    return {
        "customer_id":   customer_id,
        "accounts":      rows,
        "total_balance": total,
        "account_count": len(rows),
    }


# ─────────────────────────────────────────────────────────────────
# Tool 2 — get_customer_accounts
# ─────────────────────────────────────────────────────────────────

def get_customer_accounts(customer_id: str) -> dict:
    """
    Returns accounts grouped by product_type with per-type subtotals.

    Args:
        customer_id: Unique customer identifier.

    Returns:
        dict:
            customer_id       str
            accounts          list[{account_id, product_type, balance}]
            by_product_type   {product_type: {accounts, subtotal}}
            total_balance     float
            account_count     int
    """
    rows = _run_query(
        f"""
        SELECT
            account_id,
            product_type,
            balance
        FROM `{BQ_PREFIX}.accounts`
        WHERE customer_id = @customer_id
        ORDER BY product_type, balance DESC
        """,
        [_str_param("customer_id", customer_id)],
    )

    if not rows:
        return {
            "error": f"No accounts found for customer '{customer_id}'.",
            "customer_id": customer_id,
        }

    by_product: dict[str, dict] = {}
    for r in rows:
        pt = r.get("product_type") or "unknown"
        if pt not in by_product:
            by_product[pt] = {"accounts": [], "subtotal": 0.0}
        by_product[pt]["accounts"].append(r)
        by_product[pt]["subtotal"] = round(
            by_product[pt]["subtotal"] + (r.get("balance") or 0.0), 2
        )

    total = round(sum(g["subtotal"] for g in by_product.values()), 2)

    return {
        "customer_id":     customer_id,
        "accounts":        rows,
        "by_product_type": by_product,
        "total_balance":   total,
        "account_count":   len(rows),
    }


# ─────────────────────────────────────────────────────────────────
# Tool 3 — get_customer_summary
# ─────────────────────────────────────────────────────────────────

def get_customer_summary(customer_id: str) -> dict:
    """
    Full financial snapshot: all accounts + last 3 months of transactions.

    Args:
        customer_id: Unique customer identifier.

    Returns:
        dict:
            customer_id             str
            accounts                list
            total_balance           float
            account_count           int
            recent_transactions     list[{account_id, description,
                                          amount, type, date}]
            transaction_summary     {count, total_credits,
                                     total_debits, net_cashflow}
    """
    profile = get_customer_profile(customer_id)

    if "error" in profile:
        return profile

    account_ids = [a["account_id"] for a in profile["accounts"]]

    if not account_ids:
        return {
            **profile,
            "recent_transactions": [],
            "transaction_summary": {
                "count":         0,
                "total_credits": 0.0,
                "total_debits":  0.0,
                "net_cashflow":  0.0,
            },
        }

    # account_id values come from our own BQ result — safe to inline
    id_list = ", ".join(f"'{aid}'" for aid in account_ids)

    tx_rows = _run_query(
        f"""
        SELECT
            account_id,
            description,
            amount,
            type,
            date
        FROM `{BQ_PREFIX}.transactions`
        WHERE account_id IN ({id_list})
          AND PARSE_DATE('%Y-%m-%d', date)
              >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 MONTH)
        ORDER BY date DESC
        LIMIT 100
        """,
    )

    credits = round(
        sum(t.get("amount") or 0.0 for t in tx_rows if t.get("type") == "credit"), 2
    )
    debits = round(
        sum(t.get("amount") or 0.0 for t in tx_rows if t.get("type") == "debit"), 2
    )

    return {
        "customer_id":   customer_id,
        "accounts":      profile["accounts"],
        "total_balance": profile["total_balance"],
        "account_count": profile["account_count"],
        "recent_transactions": tx_rows,
        "transaction_summary": {
            "count":         len(tx_rows),
            "total_credits": credits,
            "total_debits":  debits,
            "net_cashflow":  round(credits - debits, 2),
        },
    }


# ─────────────────────────────────────────────────────────────────
# FunctionTool wrappers
# ─────────────────────────────────────────────────────────────────

get_profile_tool  = FunctionTool(func=get_customer_profile)
get_accounts_tool = FunctionTool(func=get_customer_accounts)
get_summary_tool  = FunctionTool(func=get_customer_summary)
