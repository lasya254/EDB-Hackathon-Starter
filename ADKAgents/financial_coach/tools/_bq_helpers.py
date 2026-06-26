# tools/_bq_helpers.py
"""
Shared BigQuery client, serialization helpers, and query runner.
All tool files import from here — single source of truth for config.
"""

import os
from datetime import date, datetime
from decimal import Decimal

from google.cloud import bigquery

# ─────────────────────────────────────────────────────────────────
# Config — loaded at import time (after load_dotenv() in agent.py)
# ─────────────────────────────────────────────────────────────────

BQ_PROJECT  = "ltc-ipnihack-prj-11"
BQ_DATASET  = "BANK_DATA"
BQ_LOCATION = "US"

if not BQ_PROJECT:
    raise EnvironmentError(
        "GOOGLE_CLOUD_PROJECT is not set.\n"
        "Add it to your .env:  GOOGLE_CLOUD_PROJECT=your-project-id"
    )
if not BQ_DATASET:
    raise EnvironmentError(
        "BQ_DATASET is not set.\n"
        "Add it to your .env:  BQ_DATASET=your_dataset_name"
    )

# Fully-qualified prefix used in every SQL query:  project.dataset
BQ_PREFIX = f"{BQ_PROJECT}.{BQ_DATASET}"

# Single shared client — pinned to BQ_LOCATION (not Vertex AI location)
bq_client = bigquery.Client(
    project=BQ_PROJECT,
    location=BQ_LOCATION,
)


# ─────────────────────────────────────────────────────────────────
# Serialization helpers
# ─────────────────────────────────────────────────────────────────

def _safe_serialize(obj):
    """
    Recursively converts BigQuery row values into JSON-safe Python types.

    Conversions:
        datetime.date / datetime.datetime  →  ISO-8601 string
        decimal.Decimal                    →  float
        dict / list                        →  recurse
        everything else                    →  unchanged
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe_serialize(i) for i in obj]
    return obj


def _rows_to_dicts(query_result) -> list[dict]:
    """Convert a BigQuery RowIterator into a list of serializable dicts."""
    return [_safe_serialize(dict(row)) for row in query_result]


# ─────────────────────────────────────────────────────────────────
# Query runner
# ─────────────────────────────────────────────────────────────────

def _run_query(sql: str, params: list | None = None) -> list[dict]:
    """
    Execute a parameterised BigQuery query and return serializable rows.

    Args:
        sql:    Standard SQL string with @param placeholders.
        params: List of bigquery.ScalarQueryParameter objects.

    Returns:
        List of dicts, fully JSON-serializable.
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=params or []
    )
    result = bq_client.query(
        sql,
        job_config=job_config,
        location=BQ_LOCATION,
    ).result()
    return _rows_to_dicts(result)


# ─────────────────────────────────────────────────────────────────
# Parameter shorthand helpers
# ─────────────────────────────────────────────────────────────────

def _str_param(name: str, value: str) -> bigquery.ScalarQueryParameter:
    """Create a STRING query parameter."""
    return bigquery.ScalarQueryParameter(name, "STRING", value)


def _int_param(name: str, value: int) -> bigquery.ScalarQueryParameter:
    """Create an INT64 query parameter."""
    return bigquery.ScalarQueryParameter(name, "INT64", value)


def _float_param(name: str, value: float) -> bigquery.ScalarQueryParameter:
    """Create a FLOAT64 query parameter."""
    return bigquery.ScalarQueryParameter(name, "FLOAT64", value)
