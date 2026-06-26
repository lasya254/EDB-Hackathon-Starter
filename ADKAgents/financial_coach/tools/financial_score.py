"""
Financial Score tools.

Calculates an overall financial health score out of 100 using:
- savings rate
- spending discipline
- debt burden
- credit utilization
- investments
- liquidity buffer
- insurance coverage

Schema used:
    accounts(account_id, customer_id, product_type, balance)
    transactions(account_id, description, amount, type, date)
    investments(investment_id, customer_id, asset_type, asset_name, invested_amount,
                current_value, monthly_sip, risk_level, category, purchase_date, status)
    loans(loan_id, customer_id, loan_type, lender_name, principal_amount,
          outstanding_amount, interest_rate, emi, tenure_months, remaining_months,
          start_date, end_date, status)
    credit_cards(card_id, customer_id, card_name, issuer, credit_limit,
                 current_outstanding, minimum_due, payment_due_date, interest_rate, status)
    fixed_deposits(fd_id, customer_id, bank_name, principal_amount, interest_rate,
                   maturity_amount, start_date, maturity_date, tenure_months, status)
    insurance(policy_id, customer_id, policy_type, policy_name, insurer, sum_assured,
              premium, frequency, start_date, end_date, nominee, status)
"""

from google.adk.tools import FunctionTool

from ._bq_helpers import BQ_PREFIX, _run_query, _str_param


def calculate_financial_score(customer_id: str) -> dict:
    """
    Calculate an overall financial health score out of 100.
    """

    cashflow_rows = _run_query(
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
            ROUND(AVG(income), 2) AS avg_monthly_income,
            ROUND(AVG(expenses), 2) AS avg_monthly_expenses,
            ROUND(AVG(income - expenses), 2) AS avg_monthly_savings,
            ROUND(AVG((income - expenses) / NULLIF(income, 0) * 100), 2) AS avg_savings_rate
        FROM monthly_cashflow
        """,
        [_str_param("customer_id", customer_id)],
    )

    spending_rows = _run_query(
        f"""
        WITH categorized_spending AS (
            SELECT
                CASE
                    WHEN REGEXP_CONTAINS(UPPER(t.description), r'BIGBASKET|DMART|BLINKIT|ZEPTO|GROCERY|MORE|SPENCERS|JIOMART|HOSPITAL|MEDICAL|PHARMACY|APOLLO|ELECTRICITY|WATER|GAS|BROADBAND|AIRTEL|JIO|VODAFONE|BSNL|SCHOOL|COLLEGE|TUITION|COURSE|EDUCATION|INSURANCE|POLICY|LIC|RENT|LANDLORD|HOUSE RENT|FUEL|PETROL|DIESEL|HPCL|IOCL|BPCL')
                        THEN 'essential'
                    ELSE 'discretionary'
                END AS spend_type,
                t.amount
            FROM `{BQ_PREFIX}.transactions` t
            JOIN `{BQ_PREFIX}.accounts` a
              ON t.account_id = a.account_id
            WHERE a.customer_id = @customer_id
              AND LOWER(t.type) = 'debit'
              AND PARSE_DATE('%Y-%m-%d', t.date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 MONTH)
        )
        SELECT
            ROUND(SUM(CASE WHEN spend_type = 'essential' THEN amount ELSE 0 END), 2) AS essential_spending,
            ROUND(SUM(CASE WHEN spend_type = 'discretionary' THEN amount ELSE 0 END), 2) AS discretionary_spending,
            ROUND(SUM(amount), 2) AS total_spending
        FROM categorized_spending
        """,
        [_str_param("customer_id", customer_id)],
    )

    debt_rows = _run_query(
        f"""
        SELECT
            ROUND(SUM(CASE WHEN status = 'active' THEN emi ELSE 0 END), 2) AS total_monthly_emi,
            ROUND(SUM(CASE WHEN status = 'active' THEN outstanding_amount ELSE 0 END), 2) AS total_outstanding_debt
        FROM `{BQ_PREFIX}.loans`
        WHERE customer_id = @customer_id
        """,
        [_str_param("customer_id", customer_id)],
    )

    card_rows = _run_query(
        f"""
        SELECT
            ROUND(SUM(CASE WHEN status = 'active' THEN credit_limit ELSE 0 END), 2) AS total_credit_limit,
            ROUND(SUM(CASE WHEN status = 'active' THEN current_outstanding ELSE 0 END), 2) AS total_card_outstanding,
            ROUND(SUM(CASE WHEN status = 'active' THEN minimum_due ELSE 0 END), 2) AS total_minimum_due
        FROM `{BQ_PREFIX}.credit_cards`
        WHERE customer_id = @customer_id
        """,
        [_str_param("customer_id", customer_id)],
    )

    investment_rows = _run_query(
        f"""
        SELECT
            COUNTIF(status = 'active') AS active_investment_count,
            ROUND(SUM(CASE WHEN status = 'active' THEN current_value ELSE 0 END), 2) AS total_investment_value,
            ROUND(SUM(CASE WHEN status = 'active' THEN monthly_sip ELSE 0 END), 2) AS total_monthly_sip,
            COUNT(DISTINCT CASE WHEN status = 'active' THEN category END) AS investment_category_count
        FROM `{BQ_PREFIX}.investments`
        WHERE customer_id = @customer_id
        """,
        [_str_param("customer_id", customer_id)],
    )

    liquidity_rows = _run_query(
        f"""
        SELECT
            ROUND(SUM(balance), 2) AS total_account_balance
        FROM `{BQ_PREFIX}.accounts`
        WHERE customer_id = @customer_id
        """,
        [_str_param("customer_id", customer_id)],
    )

    fd_rows = _run_query(
        f"""
        SELECT
            ROUND(SUM(CASE WHEN status = 'active' THEN principal_amount ELSE 0 END), 2) AS active_fd_value
        FROM `{BQ_PREFIX}.fixed_deposits`
        WHERE customer_id = @customer_id
        """,
        [_str_param("customer_id", customer_id)],
    )

    insurance_rows = _run_query(
        f"""
        SELECT
            COUNTIF(status = 'active') AS active_policy_count,
            COUNTIF(status = 'active' AND policy_type = 'health') AS health_policy_count,
            COUNTIF(status = 'active' AND policy_type = 'term_life') AS term_life_policy_count,
            COUNTIF(status = 'active' AND policy_type = 'motor') AS motor_policy_count,
            ROUND(SUM(CASE WHEN status = 'active' THEN premium ELSE 0 END), 2) AS total_active_premium
        FROM `{BQ_PREFIX}.insurance`
        WHERE customer_id = @customer_id
        """,
        [_str_param("customer_id", customer_id)],
    )

    cashflow = cashflow_rows[0] if cashflow_rows else {}
    spending = spending_rows[0] if spending_rows else {}
    debt = debt_rows[0] if debt_rows else {}
    cards = card_rows[0] if card_rows else {}
    investments = investment_rows[0] if investment_rows else {}
    liquidity = liquidity_rows[0] if liquidity_rows else {}
    fds = fd_rows[0] if fd_rows else {}
    insurance = insurance_rows[0] if insurance_rows else {}

    avg_monthly_income = float(cashflow.get("avg_monthly_income") or 0.0)
    avg_monthly_expenses = float(cashflow.get("avg_monthly_expenses") or 0.0)
    avg_monthly_savings = float(cashflow.get("avg_monthly_savings") or 0.0)
    avg_savings_rate = float(cashflow.get("avg_savings_rate") or 0.0)

    essential_spending = float(spending.get("essential_spending") or 0.0)
    discretionary_spending = float(spending.get("discretionary_spending") or 0.0)
    total_spending = float(spending.get("total_spending") or 0.0)

    total_monthly_emi = float(debt.get("total_monthly_emi") or 0.0)
    total_outstanding_debt = float(debt.get("total_outstanding_debt") or 0.0)

    total_credit_limit = float(cards.get("total_credit_limit") or 0.0)
    total_card_outstanding = float(cards.get("total_card_outstanding") or 0.0)
    total_minimum_due = float(cards.get("total_minimum_due") or 0.0)

    active_investment_count = int(investments.get("active_investment_count") or 0)
    total_investment_value = float(investments.get("total_investment_value") or 0.0)
    total_monthly_sip = float(investments.get("total_monthly_sip") or 0.0)
    investment_category_count = int(investments.get("investment_category_count") or 0)

    total_account_balance = float(liquidity.get("total_account_balance") or 0.0)
    active_fd_value = float(fds.get("active_fd_value") or 0.0)

    active_policy_count = int(insurance.get("active_policy_count") or 0)
    health_policy_count = int(insurance.get("health_policy_count") or 0)
    term_life_policy_count = int(insurance.get("term_life_policy_count") or 0)
    motor_policy_count = int(insurance.get("motor_policy_count") or 0)

    discretionary_ratio = (
        (discretionary_spending / total_spending) * 100 if total_spending else 0.0
    )
    debt_to_income = (
        ((total_monthly_emi + total_minimum_due) / avg_monthly_income) * 100
        if avg_monthly_income else 0.0
    )
    credit_utilization = (
        (total_card_outstanding / total_credit_limit) * 100
        if total_credit_limit else 0.0
    )
    liquid_balance = total_account_balance + active_fd_value
    expense_cover_months = (
        liquid_balance / avg_monthly_expenses if avg_monthly_expenses else 0.0
    )

    # 1. Savings Rate (20)
    if avg_savings_rate >= 30:
        savings_score = 20
    elif avg_savings_rate >= 20:
        savings_score = 16
    elif avg_savings_rate >= 10:
        savings_score = 10
    elif avg_savings_rate > 0:
        savings_score = 5
    else:
        savings_score = 0

    # 2. Spending Discipline (15)
    if discretionary_ratio <= 30:
        spending_score = 15
    elif discretionary_ratio <= 40:
        spending_score = 12
    elif discretionary_ratio <= 50:
        spending_score = 8
    elif discretionary_ratio <= 60:
        spending_score = 4
    else:
        spending_score = 0

    # 3. Debt Burden (20)
    if debt_to_income < 20:
        debt_score = 20
    elif debt_to_income <= 35:
        debt_score = 15
    elif debt_to_income <= 50:
        debt_score = 8
    else:
        debt_score = 0

    # 4. Credit Utilization (10)
    if total_credit_limit == 0:
        credit_score = 10
    elif credit_utilization < 30:
        credit_score = 10
    elif credit_utilization <= 50:
        credit_score = 7
    elif credit_utilization <= 75:
        credit_score = 3
    else:
        credit_score = 0

    # 5. Investments / Wealth Building (15)
    if active_investment_count >= 3 and total_monthly_sip > 0 and investment_category_count >= 2:
        investment_score = 15
    elif active_investment_count >= 2 and total_investment_value > 0:
        investment_score = 10
    elif active_investment_count >= 1:
        investment_score = 5
    else:
        investment_score = 0

    # 6. Liquidity Buffer (10)
    if expense_cover_months >= 6:
        liquidity_score = 10
    elif expense_cover_months >= 3:
        liquidity_score = 7
    elif expense_cover_months >= 1:
        liquidity_score = 4
    else:
        liquidity_score = 0

    # 7. Insurance Coverage (10)
    insurance_score = 0
    if active_policy_count > 0:
        insurance_score += 3
    if health_policy_count > 0:
        insurance_score += 3
    if term_life_policy_count > 0:
        insurance_score += 3
    if motor_policy_count > 0:
        insurance_score += 1
    insurance_score = min(insurance_score, 10)

    total_score = (
        savings_score
        + spending_score
        + debt_score
        + credit_score
        + investment_score
        + liquidity_score
        + insurance_score
    )

    if total_score >= 85:
        score_band = "excellent"
    elif total_score >= 70:
        score_band = "strong"
    elif total_score >= 55:
        score_band = "moderate"
    elif total_score >= 40:
        score_band = "weak"
    else:
        score_band = "critical"

    strengths = []
    improvements = []

    if avg_savings_rate >= 20:
        strengths.append("Healthy savings rate")
    else:
        improvements.append("Increase monthly savings rate to at least 20%")

    if discretionary_ratio <= 40 and total_spending > 0:
        strengths.append("Controlled discretionary spending")
    elif total_spending > 0:
        improvements.append("Reduce discretionary spending share")

    if debt_to_income <= 35:
        strengths.append("Manageable debt burden")
    elif total_monthly_emi > 0 or total_minimum_due > 0:
        improvements.append("Lower monthly debt burden relative to income")

    if total_credit_limit == 0 or credit_utilization < 30:
        strengths.append("Healthy credit utilization")
    elif total_credit_limit > 0:
        improvements.append("Keep credit utilization below 30%")

    if investment_score >= 10:
        strengths.append("Active wealth-building through investments")
    else:
        improvements.append("Build regular investments or SIP contributions")

    if expense_cover_months >= 3:
        strengths.append("Useful liquidity buffer")
    else:
        improvements.append("Build at least 3 months of expense buffer")

    if insurance_score >= 6:
        strengths.append("Meaningful insurance protection in place")
    else:
        improvements.append("Improve health and life insurance coverage")

    return {
        "customer_id": customer_id,
        "financial_score": total_score,
        "financial_score_percentage": total_score,
        "score_band": score_band,
        "component_scores": {
            "savings_rate": {"score": savings_score, "max": 20},
            "spending_discipline": {"score": spending_score, "max": 15},
            "debt_burden": {"score": debt_score, "max": 20},
            "credit_utilization": {"score": credit_score, "max": 10},
            "investments": {"score": investment_score, "max": 15},
            "liquidity_buffer": {"score": liquidity_score, "max": 10},
            "insurance_coverage": {"score": insurance_score, "max": 10},
        },
        "summary": {
            "avg_monthly_income": round(avg_monthly_income, 2),
            "avg_monthly_expenses": round(avg_monthly_expenses, 2),
            "avg_monthly_savings": round(avg_monthly_savings, 2),
            "avg_savings_rate": round(avg_savings_rate, 2),
            "essential_spending": round(essential_spending, 2),
            "discretionary_spending": round(discretionary_spending, 2),
            "discretionary_ratio": round(discretionary_ratio, 2),
            "total_monthly_emi": round(total_monthly_emi, 2),
            "total_minimum_due": round(total_minimum_due, 2),
            "debt_to_income": round(debt_to_income, 2),
            "credit_utilization": round(credit_utilization, 2),
            "liquid_balance": round(liquid_balance, 2),
            "expense_cover_months": round(expense_cover_months, 2),
            "active_investment_count": active_investment_count,
            "total_investment_value": round(total_investment_value, 2),
            "total_monthly_sip": round(total_monthly_sip, 2),
            "active_policy_count": active_policy_count,
        },
        "strengths": strengths[:5],
        "improvements": improvements[:5],
    }


calculate_financial_score_tool = FunctionTool(func=calculate_financial_score)
