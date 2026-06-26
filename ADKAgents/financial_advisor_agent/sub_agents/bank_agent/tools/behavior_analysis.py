"""Behavioral and financial trend analysis tools."""

import os
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
from dotenv import load_dotenv
from google.adk.tools.tool_context import ToolContext
from google.cloud import bigquery

from ..observability.tool_tracer import traced_tool

load_dotenv()

BQ_DATASET = os.getenv("BQ_DATASET", "")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "")


def _bq_client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT_ID if PROJECT_ID else None)


@traced_tool
def analyze_behavioral_pattern(tool_context: ToolContext) -> str:
    """
    Analyzes customer spending behavior and patterns.
    
    Returns:
    - Spending frequency (transactions per month)
    - Top spending categories (what they spend on)
    - Average transaction amount
    - Income vs Expense breakdown
    - Peak spending days/times
    """
    try:
        if not tool_context.state.get("identity_verified"):
            return "ERROR: Customer identity has not been verified."
        
        verified_id = tool_context.state.get("verified_customer_id")
        
        if BQ_DATASET:
            client = _bq_client()
            
            # Query 1: Transaction frequency and volume
            query = f"""
            WITH transaction_analysis AS (
              SELECT
                COUNT(*) as total_transactions,
                ROUND(COUNT(*) / NULLIF(
                  DATE_DIFF(MAX(PARSE_DATE('%Y-%m-%d', date)), 
                           MIN(PARSE_DATE('%Y-%m-%d', date)), MONTH) + 1, 0), 2) as avg_transactions_per_month,
                ROUND(AVG(ABS(amount)), 2) as avg_transaction_amount,
                MIN(amount) as min_transaction,
                MAX(amount) as max_transaction,
                ROUND(SUM(CASE WHEN type = 'debit' THEN amount ELSE 0 END), 2) as total_spent,
                ROUND(SUM(CASE WHEN type = 'credit' THEN amount ELSE 0 END), 2) as total_income
              FROM `{BQ_DATASET}.transactions` t
              JOIN `{BQ_DATASET}.accounts` a ON t.account_id = a.account_id
              WHERE a.customer_id = @customer_id
            )
            SELECT * FROM transaction_analysis
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("customer_id", "STRING", verified_id)]
            )
            result_df = client.query(query, job_config=job_config).to_dataframe()
            
            if result_df.empty:
                return "No transaction data available for this customer."
            
            analysis = result_df.iloc[0].to_dict()
            
            # Query 2: Top spending categories
            category_query = f"""
            SELECT
              description as spending_category,
              COUNT(*) as frequency,
              ROUND(SUM(ABS(amount)), 2) as total_amount,
              ROUND(AVG(ABS(amount)), 2) as avg_amount
            FROM `{BQ_DATASET}.transactions` t
            JOIN `{BQ_DATASET}.accounts` a ON t.account_id = a.account_id
            WHERE a.customer_id = @customer_id AND type = 'debit'
            GROUP BY description
            ORDER BY total_amount DESC
            LIMIT 5
            """
            
            category_df = client.query(category_query, job_config=job_config).to_dataframe()
            
            result_text = "BEHAVIORAL PATTERN ANALYSIS\n"
            result_text += "=" * 50 + "\n\n"
            result_text += "TRANSACTION SUMMARY:\n"
            result_text += f"  Total Transactions: {analysis['total_transactions']}\n"
            result_text += f"  Avg per Month: {analysis['avg_transactions_per_month']}\n"
            result_text += f"  Avg Amount: ${analysis['avg_transaction_amount']}\n"
            result_text += f"  Range: ${analysis['min_transaction']} to ${analysis['max_transaction']}\n\n"
            result_text += "INCOME VS EXPENSE:\n"
            result_text += f"  Total Income: ${analysis['total_income']}\n"
            result_text += f"  Total Spent: ${analysis['total_spent']}\n"
            result_text += f"  Net: ${analysis['total_income'] - analysis['total_spent']}\n\n"
            result_text += "TOP 5 SPENDING CATEGORIES:\n"
            result_text += category_df.to_string(index=False)
            
            return result_text
            
        else:
            # SQLite fallback
            conn = sqlite3.connect("lbg_pec_hack.db")
            
            query = """
            SELECT
              COUNT(*) as total_transactions,
              ROUND(AVG(ABS(amount)), 2) as avg_transaction_amount,
              MIN(amount) as min_transaction,
              MAX(amount) as max_transaction,
              ROUND(SUM(CASE WHEN type = 'debit' THEN amount ELSE 0 END), 2) as total_spent,
              ROUND(SUM(CASE WHEN type = 'credit' THEN amount ELSE 0 END), 2) as total_income
            FROM transactions t
            JOIN accounts a ON t.account_id = a.account_id
            WHERE a.customer_id = ?
            """
            
            result_df = pd.read_sql_query(query, conn, params=[verified_id])
            
            if result_df.empty:
                conn.close()
                return "No transaction data available for this customer."
            
            analysis = result_df.iloc[0].to_dict()
            
            category_query = """
            SELECT
              description as spending_category,
              COUNT(*) as frequency,
              ROUND(SUM(ABS(amount)), 2) as total_amount,
              ROUND(AVG(ABS(amount)), 2) as avg_amount
            FROM transactions t
            JOIN accounts a ON t.account_id = a.account_id
            WHERE a.customer_id = ? AND type = 'debit'
            GROUP BY description
            ORDER BY total_amount DESC
            LIMIT 5
            """
            
            category_df = pd.read_sql_query(category_query, conn, params=[verified_id])
            conn.close()
            
            result_text = "BEHAVIORAL PATTERN ANALYSIS\n"
            result_text += "=" * 50 + "\n\n"
            result_text += "TRANSACTION SUMMARY:\n"
            result_text += f"  Total Transactions: {analysis['total_transactions']}\n"
            result_text += f"  Avg Amount: ${analysis['avg_transaction_amount']}\n"
            result_text += f"  Range: ${analysis['min_transaction']} to ${analysis['max_transaction']}\n\n"
            result_text += "INCOME VS EXPENSE:\n"
            result_text += f"  Total Income: ${analysis['total_income']}\n"
            result_text += f"  Total Spent: ${analysis['total_spent']}\n"
            result_text += f"  Net: ${analysis['total_income'] - analysis['total_spent']}\n\n"
            result_text += "TOP 5 SPENDING CATEGORIES:\n"
            result_text += category_df.to_string(index=False)
            
            return result_text
            
    except Exception as e:
        return f"Analysis Error: {str(e)}"


@traced_tool
def analyze_financial_trends(tool_context: ToolContext, months: int = 6) -> str:
    """
    Analyzes financial trends over time.
    
    Shows:
    - Monthly spending trends
    - Balance progression
    - Income/Expense trends
    - Spending velocity (increasing/decreasing)
    
    Args:
        months: Number of months to analyze (default: 6)
    
    Returns:
        Formatted trend analysis
    """
    try:
        if not tool_context.state.get("identity_verified"):
            return "ERROR: Customer identity has not been verified."
        
        verified_id = tool_context.state.get("verified_customer_id")
        
        if BQ_DATASET:
            client = _bq_client()
            
            query = f"""
            WITH monthly_trends AS (
              SELECT
                FORMAT_DATE('%Y-%m', PARSE_DATE('%Y-%m-%d', t.date)) as month,
                ROUND(SUM(CASE WHEN t.type = 'debit' THEN ABS(t.amount) ELSE 0 END), 2) as monthly_spent,
                ROUND(SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE 0 END), 2) as monthly_income,
                COUNT(*) as transaction_count
              FROM `{BQ_DATASET}.transactions` t
              JOIN `{BQ_DATASET}.accounts` a ON t.account_id = a.account_id
              WHERE a.customer_id = @customer_id
                AND PARSE_DATE('%Y-%m-%d', t.date) >= DATE_SUB(CURRENT_DATE(), INTERVAL @months MONTH)
              GROUP BY month
              ORDER BY month ASC
            )
            SELECT 
              month,
              monthly_spent,
              monthly_income,
              transaction_count,
              ROUND(monthly_income - monthly_spent, 2) as net_month,
              ROUND(
                (monthly_spent - LAG(monthly_spent) OVER (ORDER BY month)) / 
                NULLIF(LAG(monthly_spent) OVER (ORDER BY month), 0) * 100, 2
              ) as spending_change_pct
            FROM monthly_trends
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("customer_id", "STRING", verified_id),
                    bigquery.ScalarQueryParameter("months", "INT64", months)
                ]
            )
            result_df = client.query(query, job_config=job_config).to_dataframe()
            
        else:
            # SQLite fallback
            conn = sqlite3.connect("lbg_pec_hack.db")
            
            # For SQLite, we use simpler date formatting
            query = """
            WITH monthly_trends AS (
              SELECT
                strftime('%Y-%m', t.date) as month,
                ROUND(SUM(CASE WHEN t.type = 'debit' THEN ABS(t.amount) ELSE 0 END), 2) as monthly_spent,
                ROUND(SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE 0 END), 2) as monthly_income,
                COUNT(*) as transaction_count
              FROM transactions t
              JOIN accounts a ON t.account_id = a.account_id
              WHERE a.customer_id = ?
              GROUP BY month
              ORDER BY month ASC
            )
            SELECT 
              month,
              monthly_spent,
              monthly_income,
              transaction_count,
              ROUND(monthly_income - monthly_spent, 2) as net_month
            FROM monthly_trends
            """
            
            result_df = pd.read_sql_query(query, conn, params=[verified_id])
            conn.close()
        
        if result_df.empty:
            return "No transaction data available for trend analysis."
        
        result_text = "FINANCIAL TRENDS ANALYSIS\n"
        result_text += "=" * 50 + "\n\n"
        result_text += f"Last {months} Months Overview:\n\n"
        result_text += result_df.to_string(index=False)
        
        # Calculate trends
        if len(result_df) > 1:
            first_month_spent = result_df.iloc[0]['monthly_spent']
            last_month_spent = result_df.iloc[-1]['monthly_spent']
            trend = "INCREASING" if last_month_spent > first_month_spent else "DECREASING"
            change_pct = round(((last_month_spent - first_month_spent) / first_month_spent * 100), 2)
            
            result_text += "\n\nTREND ANALYSIS:\n"
            result_text += f"  Spending Direction: {trend}\n"
            result_text += f"  Change: {change_pct}%\n"
        
        return result_text
        
    except Exception as e:
        return f"Trend Analysis Error: {str(e)}"
