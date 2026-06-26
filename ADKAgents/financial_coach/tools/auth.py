"""
Customer Authentication Tool
Uses the last 4 digits of the customer's first account_id as the PIN challenge.
e.g. account_id = "ACC0001"  →  PIN = "0001"
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from google.cloud import bigquery

bq = bigquery.Client()

PROJECT        = "ltc-ipnihack-prj-11"
DS             = "BANK_DATA"
AUTH_TABLE     = f"`{PROJECT}.{DS}.auth_sessions`"
ACCOUNTS_TABLE = f"`{PROJECT}.{DS}.accounts`"

MAX_ATTEMPTS     = 3
SESSION_TTL_MINS = 30


# ── internal helpers ──────────────────────────────────────────────

def _hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def _run(sql: str, **params) -> list[dict]:
    job_params = []
    for name, val in params.items():
        if isinstance(val, int):
            job_params.append(bigquery.ScalarQueryParameter(name, "INT64", val))
        elif isinstance(val, bool):
            job_params.append(bigquery.ScalarQueryParameter(name, "BOOL", val))
        else:
            job_params.append(bigquery.ScalarQueryParameter(name, "STRING", str(val)))
    cfg = bigquery.QueryJobConfig(query_parameters=job_params)
    return [dict(row) for row in bq.query(sql, job_config=cfg).result()]


def _get_customer_pin(customer_id: str) -> str | None:
    """
    Returns the last 4 chars of the customer's first account_id,
    or None if the customer doesn't exist.
    """
    rows = _run(
        f"""
        SELECT MIN(account_id) AS ref_account
        FROM {ACCOUNTS_TABLE}
        WHERE customer_id = @customer_id
        """,
        customer_id=customer_id,
    )
    if not rows or not rows[0]["ref_account"]:
        return None
    return rows[0]["ref_account"][-4:]   # e.g. "ACC0001" → "0001"


# ── public tools ─────────────────────────────────────────────────

def initiate_auth(customer_id: str) -> dict:
    """
    Step 1 — Start an auth session for the customer.
    Call this when the user provides their customer ID.

    Returns the session_id and the challenge question to ask the user.
    Does NOT reveal the answer.

    Args:
        customer_id: e.g. 'C1001'
    """
    pin = _get_customer_pin(customer_id)
    if pin is None:
        return {
            "status":  "customer_not_found",
            "message": "No account found for this customer ID. Please check and try again.",
        }

    session_id = str(uuid.uuid4())
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MINS)).isoformat()

    _run(
        f"""
        INSERT INTO {AUTH_TABLE}
            (session_id, customer_id, created_at, expires_at,
             is_verified, attempts, challenge_type, challenge_hash)
        VALUES
            (@session_id, @customer_id, CURRENT_TIMESTAMP(), @expires_at,
             FALSE, 0, 'account_pin', @challenge_hash)
        """,
        session_id=session_id,
        customer_id=customer_id,
        expires_at=expires_at,
        challenge_hash=_hash(pin),
    )

    return {
        "status":     "challenge_issued",
        "session_id": session_id,
        "challenge":  "Please enter the last 4 digits of your account number to verify your identity.",
    }


def verify_auth(session_id: str, customer_id: str, answer: str) -> dict:
    """
    Step 2 — Verify the customer's answer.
    Call this when the user responds to the challenge.

    Args:
        session_id:  Returned by initiate_auth.
        customer_id: Must match the session.
        answer:      What the user typed (raw, will be hashed internally).
    """
    rows = _run(
        f"""
        SELECT is_verified, attempts, challenge_hash, expires_at
        FROM {AUTH_TABLE}
        WHERE session_id  = @session_id
          AND customer_id = @customer_id
        """,
        session_id=session_id,
        customer_id=customer_id,
    )

    if not rows:
        return {
            "status":  "not_found",
            "message": "Session not found. Please start over.",
        }

    s = rows[0]

    # Already verified
    if s["is_verified"]:
        return {"status": "verified", "message": "Already authenticated."}

    # Expired
    expires = s["expires_at"]
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    if datetime.now(timezone.utc) > expires.replace(tzinfo=timezone.utc):
        return {
            "status":  "expired",
            "message": "Session expired. Please start over.",
        }

    # Locked
    if s["attempts"] >= MAX_ATTEMPTS:
        return {
            "status":  "locked",
            "message": "Too many failed attempts. Please contact customer support.",
        }

    # Check answer
    if _hash(answer) == s["challenge_hash"]:
        _run(
            f"""
            UPDATE {AUTH_TABLE}
            SET is_verified = TRUE,
                verified_at = CURRENT_TIMESTAMP()
            WHERE session_id = @session_id
            """,
            session_id=session_id,
        )
        return {"status": "verified", "message": "Identity verified. Welcome!"}

    # Wrong answer
    new_attempts = s["attempts"] + 1
    _run(
        f"""
        UPDATE {AUTH_TABLE}
        SET attempts = @attempts
        WHERE session_id = @session_id
        """,
        session_id=session_id,
        attempts=new_attempts,
    )

    remaining = MAX_ATTEMPTS - new_attempts
    if remaining <= 0:
        return {
            "status":  "locked",
            "message": "Too many failed attempts. Please contact customer support.",
        }

    return {
        "status":            "failed",
        "message":           f"Incorrect PIN. {remaining} attempt(s) remaining.",
        "attempts_remaining": remaining,
    }


def check_session(session_id: str, customer_id: str) -> dict:
    """
    Gate check — call this before returning ANY financial data.
    Returns whether the session is still valid and verified.

    Args:
        session_id:  Active session ID.
        customer_id: Must match the session.
    """
    rows = _run(
        f"""
        SELECT is_verified, expires_at
        FROM {AUTH_TABLE}
        WHERE session_id  = @session_id
          AND customer_id = @customer_id
        """,
        session_id=session_id,
        customer_id=customer_id,
    )

    if not rows:
        return {"authenticated": False, "reason": "session_not_found"}

    s = rows[0]

    if not s["is_verified"]:
        return {"authenticated": False, "reason": "not_verified"}

    expires = s["expires_at"]
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    if datetime.now(timezone.utc) > expires.replace(tzinfo=timezone.utc):
        return {"authenticated": False, "reason": "session_expired"}

    return {"authenticated": True, "reason": "ok"}
