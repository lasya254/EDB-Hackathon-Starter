# financial_coach/tools/spending.py
"""
Spending Analysis Agent tools.

Schema used:
    accounts(account_id, customer_id, product_type, balance)
    transactions(account_id, description, amount, type, date)

Notes:
- No merchant_categories table is assumed.
- Categories are inferred from transaction description using CASE rules.
- Transactions are account-level, so we join accounts -> transactions on account_id.
- dates are stored as STRING in YYYY-MM-DD format, so we PARSE_DATE them.
"""

from google.adk.tools import FunctionTool

from ._bq_helpers import BQ_PREFIX, _run_query, _str_param, _int_param


def get_monthly_spending_breakdown(customer_id: str, months: int = 3) -> dict:
    """
    Analyze debit spending by inferred category for the last N months.
    """
    rows = _run_query(
        f"""
        WITH categorized_transactions AS (
            SELECT
                a.customer_id,
                PARSE_DATE('%Y-%m-%d', t.date) AS transaction_date,
                t.amount,
                t.description,
                CASE
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'UBER|OLA|RAPIDO|METRO|FUEL|PETROL|DIESEL|HPCL|IOCL|BPCL')
                        THEN 'Transport'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'BIGBASKET|DMART|BLINKIT|ZEPTO|GROCERY|MORE|SPENCERS|JIOMART')
                        THEN 'Groceries'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'ZOMATO|SWIGGY|RESTAURANT|CAFE|PIZZA|DOMINOS|MCDONALD|KFC')
                        THEN 'Food'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'AMAZON|FLIPKART|MYNTRA|SHOP|STORE|MALL')
                        THEN 'Shopping'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'NETFLIX|PRIME|HOTSTAR|SPOTIFY|YOUTUBE|BOOKMYSHOW|ENTERTAINMENT')
                        THEN 'Entertainment'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'HOSPITAL|MEDICAL|PHARMACY|APOLLO|CLINIC|HEALTH')
                        THEN 'Healthcare'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'ELECTRICITY|WATER|GAS|BROADBAND|AIRTEL|JIO|VODAFONE|BSNL|UTILITY')
                        THEN 'Utilities'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'SCHOOL|COLLEGE|TUITION|COURSE|EDUCATION|UDEMY|COURSERA')
                        THEN 'Education'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'INSURANCE|POLICY|LIC|HDFC LIFE|ICICI PRU|PREMIUM')
                        THEN 'Insurance'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'RENT|LANDLORD|HOUSE RENT')
                        THEN 'Housing'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'ATM|CASH')
                        THEN 'Cash Withdrawal'
                    ELSE 'Uncategorized'
                END AS category,
                CASE
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'BIGBASKET|DMART|BLINKIT|ZEPTO|GROCERY|MORE|SPENCERS|JIOMART')
                        THEN 'Supermarket'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'ZOMATO|SWIGGY')
                        THEN 'Food Delivery'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'UBER|OLA|RAPIDO')
                        THEN 'Ride Hailing'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'FUEL|PETROL|DIESEL|HPCL|IOCL|BPCL')
                        THEN 'Fuel'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'NETFLIX|PRIME|HOTSTAR|SPOTIFY')
                        THEN 'Subscriptions'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'ELECTRICITY|WATER|GAS')
                        THEN 'Bills'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'AIRTEL|JIO|VODAFONE|BSNL|BROADBAND')
                        THEN 'Telecom'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'HOSPITAL|MEDICAL|PHARMACY|APOLLO')
                        THEN 'Medical'
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'AMAZON|FLIPKART|MYNTRA')
                        THEN 'E-commerce'
                    ELSE 'Other'
                END AS subcategory,
                CASE
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'BIGBASKET|DMART|BLINKIT|ZEPTO|GROCERY|MORE|SPENCERS|JIOMART|HOSPITAL|MEDICAL|PHARMACY|APOLLO|ELECTRICITY|WATER|GAS|BROADBAND|AIRTEL|JIO|VODAFONE|BSNL|SCHOOL|COLLEGE|TUITION|COURSE|EDUCATION|INSURANCE|POLICY|LIC|RENT|LANDLORD|HOUSE RENT|FUEL|PETROL|DIESEL|HPCL|IOCL|BPCL')
                        THEN TRUE
                    ELSE FALSE
                END AS is_essential,
                FORMAT_DATE('%Y-%m', PARSE_DATE('%Y-%m-%d', t.date)) AS month
            FROM `{BQ_PREFIX}.transactions` t
            JOIN `{BQ_PREFIX}.accounts` a
              ON t.account_id = a.account_id
            WHERE a.customer_id = @customer_id
              AND LOWER(t.type) = 'debit'
              AND PARSE_DATE('%Y-%m-%d', t.date) >= DATE_SUB(CURRENT_DATE(), INTERVAL @months MONTH)
        )
        SELECT
            month,
            category,
            subcategory,
            is_essential,
            COUNT(*) AS transaction_count,
            ROUND(SUM(amount), 2) AS total_amount,
            ROUND(AVG(amount), 2) AS avg_transaction
        FROM categorized_transactions
        GROUP BY month, category, subcategory, is_essential
        ORDER BY month DESC, total_amount DESC
        """,
        [
            _str_param("customer_id", customer_id),
            _int_param("months", months),
        ],
    )

    monthly_spending: dict[str, dict] = {}
    for row in rows:
        month = row["month"]
        if month not in monthly_spending:
            monthly_spending[month] = {
                "categories": [],
                "total_spending": 0.0,
                "essential_spending": 0.0,
                "discretionary_spending": 0.0,
            }

        amount = float(row.get("total_amount") or 0.0)
        is_essential = bool(row.get("is_essential") or False)

        monthly_spending[month]["categories"].append({
            "category": row["category"],
            "subcategory": row["subcategory"],
            "amount": amount,
            "count": int(row.get("transaction_count") or 0),
            "avg_transaction": float(row.get("avg_transaction") or 0.0),
            "is_essential": is_essential,
        })

        monthly_spending[month]["total_spending"] = round(
            monthly_spending[month]["total_spending"] + amount, 2
        )

        if is_essential:
            monthly_spending[month]["essential_spending"] = round(
                monthly_spending[month]["essential_spending"] + amount, 2
            )
        else:
            monthly_spending[month]["discretionary_spending"] = round(
                monthly_spending[month]["discretionary_spending"] + amount, 2
            )

    grand_total = round(
        sum(m["total_spending"] for m in monthly_spending.values()), 2
    )

    return {
        "customer_id": customer_id,
        "months": months,
        "monthly_spending": monthly_spending,
        "summary": {
            "months_analyzed": len(monthly_spending),
            "total_spending": grand_total,
        },
    }


def get_spending_trends(customer_id: str) -> dict:
    """
    Identify 6-month spending trends for debit transactions.
    """
    rows = _run_query(
        f"""
        WITH monthly_totals AS (
            SELECT
                FORMAT_DATE('%Y-%m', PARSE_DATE('%Y-%m-%d', t.date)) AS month,
                SUM(t.amount) AS total_spending,
                COUNT(*) AS transaction_count
            FROM `{BQ_PREFIX}.transactions` t
            JOIN `{BQ_PREFIX}.accounts` a
              ON t.account_id = a.account_id
            WHERE a.customer_id = @customer_id
              AND LOWER(t.type) = 'debit'
              AND PARSE_DATE('%Y-%m-%d', t.date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 6 MONTH)
            GROUP BY month
        ),
        with_lag AS (
            SELECT
                month,
                total_spending,
                transaction_count,
                LAG(total_spending) OVER (ORDER BY month) AS prev_month_spending,
                AVG(total_spending) OVER (
                    ORDER BY month
                    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                ) AS moving_avg
            FROM monthly_totals
        )
        SELECT
            month,
            ROUND(total_spending, 2) AS total_spending,
            transaction_count,
            ROUND(prev_month_spending, 2) AS prev_month_spending,
            ROUND(moving_avg, 2) AS moving_avg,
            ROUND(
                (total_spending - prev_month_spending) / NULLIF(prev_month_spending, 0) * 100,
                2
            ) AS mom_change_pct,
            CASE
                WHEN total_spending > moving_avg * 1.2 THEN 'spike'
                WHEN total_spending < moving_avg * 0.8 THEN 'drop'
                ELSE 'normal'
            END AS trend_flag
        FROM with_lag
        ORDER BY month DESC
        """,
        [_str_param("customer_id", customer_id)],
    )

    if len(rows) >= 2:
        first_month = float(rows[-1].get("total_spending") or 0.0)
        last_month = float(rows[0].get("total_spending") or 0.0)
        overall_trend = "increasing" if last_month > first_month else "decreasing"
        overall_change = round(
            ((last_month - first_month) / first_month) * 100, 2
        ) if first_month else 0.0
    else:
        overall_trend = "insufficient_data"
        overall_change = 0.0

    return {
        "customer_id": customer_id,
        "monthly_trends": rows,
        "overall_trend": overall_trend,
        "overall_change_pct": overall_change,
    }


def get_top_merchants(customer_id: str, limit: int = 10) -> dict:
    """
    Return top spending descriptions by debit spend over last 3 months.
    """
    rows = _run_query(
        f"""
        SELECT
            t.description AS merchant,
            COUNT(*) AS transaction_count,
            ROUND(SUM(t.amount), 2) AS total_spent,
            ROUND(AVG(t.amount), 2) AS avg_transaction,
            MIN(PARSE_DATE('%Y-%m-%d', t.date)) AS first_transaction,
            MAX(PARSE_DATE('%Y-%m-%d', t.date)) AS last_transaction
        FROM `{BQ_PREFIX}.transactions` t
        JOIN `{BQ_PREFIX}.accounts` a
          ON t.account_id = a.account_id
        WHERE a.customer_id = @customer_id
          AND LOWER(t.type) = 'debit'
          AND PARSE_DATE('%Y-%m-%d', t.date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 MONTH)
        GROUP BY t.description
        ORDER BY total_spent DESC
        LIMIT @limit
        """,
        [
            _str_param("customer_id", customer_id),
            _int_param("limit", limit),
        ],
    )

    return {
        "customer_id": customer_id,
        "top_merchants": rows,
        "analysis_period": "last_3_months",
    }


def get_recurring_expenses(customer_id: str) -> dict:
    """
    Identify recurring spending descriptions over the last 6 months.
    """
    rows = _run_query(
        f"""
        WITH monthly_merchant_spending AS (
            SELECT
                t.description AS merchant,
                FORMAT_DATE('%Y-%m', PARSE_DATE('%Y-%m-%d', t.date)) AS month,
                SUM(t.amount) AS monthly_amount,
                COUNT(*) AS monthly_count
            FROM `{BQ_PREFIX}.transactions` t
            JOIN `{BQ_PREFIX}.accounts` a
              ON t.account_id = a.account_id
            WHERE a.customer_id = @customer_id
              AND LOWER(t.type) = 'debit'
              AND PARSE_DATE('%Y-%m-%d', t.date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 6 MONTH)
            GROUP BY merchant, month
        ),
        recurring_candidates AS (
            SELECT
                merchant,
                COUNT(DISTINCT month) AS months_present,
                ROUND(AVG(monthly_amount), 2) AS avg_monthly,
                ROUND(STDDEV(monthly_amount), 2) AS amount_stddev,
                ROUND(SUM(monthly_amount), 2) AS total_spent
            FROM monthly_merchant_spending
            GROUP BY merchant
            HAVING COUNT(DISTINCT month) >= 3
        )
        SELECT
            merchant,
            months_present,
            avg_monthly,
            amount_stddev,
            total_spent,
            CASE
                WHEN amount_stddev / NULLIF(avg_monthly, 0) < 0.1 THEN 'fixed'
                ELSE 'variable'
            END AS expense_type
        FROM recurring_candidates
        ORDER BY avg_monthly DESC
        """,
        [_str_param("customer_id", customer_id)],
    )

    total_recurring = round(
        sum(float(r.get("avg_monthly") or 0.0) for r in rows),
        2,
    )

    return {
        "customer_id": customer_id,
        "recurring_expenses": rows,
        "total_monthly_recurring": total_recurring,
        "count": len(rows),
    }


def calculate_savings_rate(customer_id: str) -> dict:
    """
    Calculate monthly savings rate from credits vs debits over last 6 months.
    """
    rows = _run_query(
        f"""
        WITH monthly_cashflow AS (
            SELECT
                FORMAT_DATE('%Y-%m', PARSE_DATE('%Y-%m-%d', t.date)) AS month,
                SUM(CASE WHEN LOWER(t.type) = 'credit' THEN t.amount ELSE 0 END) AS income,
                SUM(CASE WHEN LOWER(t.type) = 'debit' THEN t.amount ELSE 0 END) AS expenses
            FROM `{BQ_PREFIX}.transactions` t
            JOIN `{BQ_PREFIX}.accounts` a
              ON t.account_id = a.account_id
            WHERE a.customer_id = @customer_id
              AND PARSE_DATE('%Y-%m-%d', t.date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 6 MONTH)
            GROUP BY month
        )
        SELECT
            month,
            ROUND(income, 2) AS income,
            ROUND(expenses, 2) AS expenses,
            ROUND(income - expenses, 2) AS savings,
            ROUND((income - expenses) / NULLIF(income, 0) * 100, 2) AS savings_rate
        FROM monthly_cashflow
        ORDER BY month DESC
        """,
        [_str_param("customer_id", customer_id)],
    )

    if rows:
        avg_savings_rate = sum(float(r.get("savings_rate") or 0.0) for r in rows) / len(rows)
        avg_savings = sum(float(r.get("savings") or 0.0) for r in rows) / len(rows)
    else:
        avg_savings_rate = 0.0
        avg_savings = 0.0

    if avg_savings_rate >= 30:
        health = "excellent"
    elif avg_savings_rate >= 20:
        health = "good"
    elif avg_savings_rate >= 10:
        health = "moderate"
    else:
        health = "needs_improvement"

    return {
        "customer_id": customer_id,
        "monthly_breakdown": rows,
        "average_savings_rate": round(avg_savings_rate, 2),
        "average_monthly_savings": round(avg_savings, 2),
        "savings_health": health,
    }


get_monthly_spending_breakdown_tool = FunctionTool(func=get_monthly_spending_breakdown)
get_spending_trends_tool = FunctionTool(func=get_spending_trends)
get_top_merchants_tool = FunctionTool(func=get_top_merchants)
get_recurring_expenses_tool = FunctionTool(func=get_recurring_expenses)
calculate_savings_rate_tool = FunctionTool(func=calculate_savings_rate)
