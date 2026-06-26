"""ADK model callbacks for observability + auth gating.

Implements ``before_model_callback`` and ``after_model_callback`` to capture
LLM inputs/outputs, token usage, latency, and cost.

Also enforces authentication before customer-specific sensitive financial queries.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse

from .config import LOG_LLM_CONTENT, get_pricing
from .metrics import LlmCallRecord, store
from ..tools.auth import check_session
try:
    from opentelemetry import trace as otel_trace
    _tracer = otel_trace.get_tracer("bank_agent.observability")
except ImportError:
    _tracer = None  # type: ignore[assignment]

logger = logging.getLogger("bank_agent.observability")

_START_KEY = "_obs_llm_start_ns"

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

SENSITIVE_KEYWORDS = [
    "financial",
    "report",
    "score",
    "summary",
    "account",
    "balance",
    "transaction",
    "transactions",
    "spending",
    "spend",
    "spent",
    "expense",
    "expenses",
    "expenditure",
    "budget",
    "cashflow",
    "income",
    "savings",
    "investment",
    "investments",
    "portfolio",
    "loan",
    "loans",
    "emi",
    "credit card",
    "credit cards",
    "debt",
    "fd",
    "fixed deposit",
    "insurance",
    "premium",
    "net worth",
]


def _extract_customer_id(text: str) -> str | None:
    """Extract customer ID like C1001 from user text."""
    if not text:
        return None
    match = re.search(r"\bC\d{4,}\b", text, re.IGNORECASE)
    return match.group(0).upper() if match else None

def _requires_auth(text: str, customer_id: str | None) -> bool:
    """Customer-specific financial queries must always authenticate."""
    if not text or not customer_id:
        return False

    lower = text.lower()
    return any(keyword in lower for keyword in SENSITIVE_KEYWORDS)

def _force_auth_response(message: str) -> LlmResponse:
    """
    Return an immediate model response to stop routing and force auth flow.
    This avoids letting the root agent continue to another sub-agent.
    """
    return LlmResponse(
        content={
            "role": "model",
            "parts": [{"text": message}],
        }
    )


# ---------------------------------------------------------------------------
# Observability helpers
# ---------------------------------------------------------------------------

def _extract_last_user_text(llm_request: LlmRequest) -> str:
    """Best-effort extraction of the most recent user message text."""
    try:
        if llm_request.contents:
            last = llm_request.contents[-1]
            if hasattr(last, "parts") and last.parts:
                texts = [p.text for p in last.parts if hasattr(p, "text") and p.text]
                return " ".join(texts)[:500]
    except Exception:
        pass
    return ""


def _extract_response_text(llm_response: LlmResponse) -> str:
    """Best-effort extraction of the model response text."""
    try:
        if llm_response.content and llm_response.content.parts:
            texts = [
                p.text
                for p in llm_response.content.parts
                if hasattr(p, "text") and p.text
            ]
            return " ".join(texts)[:500]
    except Exception:
        pass
    return ""


def _session_id_from_ctx(callback_context: CallbackContext) -> str:
    """Extract a session identifier from the callback context."""
    try:
        session = callback_context.session
        if session is not None:
            return str(session.id or "unknown")
    except Exception:
        pass
    return "unknown"


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def before_model_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """Stamp start time, snapshot prompt, and enforce auth for sensitive requests."""
    callback_context.state[_START_KEY] = time.perf_counter_ns()

    user_text = _extract_last_user_text(llm_request)

    if LOG_LLM_CONTENT:
        callback_context.state["_obs_last_prompt"] = user_text

    # -------------------------------------------------------------------
    # AUTH GATE
    # -------------------------------------------------------------------
    customer_id = _extract_customer_id(user_text)
    is_sensitive = _requires_auth(user_text, customer_id)

    # Persist customer_id if found
    if customer_id:
        callback_context.state["customer_id"] = customer_id

    # Read session info from state
    session_id = callback_context.state.get("auth_session_id")
    state_customer_id = callback_context.state.get("customer_id")

    if customer_id and is_sensitive:
        # No auth session yet -> stop and ask user to authenticate
        if not session_id:
            callback_context.state["pending_customer_id"] = customer_id
            callback_context.state["auth_required"] = True
            callback_context.state["original_request"] = user_text

            return _force_auth_response(
                f"Before I can share any financial details for {customer_id}, I need to verify your identity. "
                f"Please continue with authentication first."
            )

        # Validate existing session
        try:
            auth_result = check_session(session_id=session_id, customer_id=state_customer_id or customer_id)
        except Exception as e:
            logger.exception("Auth session check failed: %s", e)
            callback_context.state["auth_required"] = True
            return _force_auth_response(
                "I could not validate your session right now. Please authenticate again."
            )

        if not auth_result.get("authenticated"):
            callback_context.state["auth_required"] = True
            callback_context.state["pending_customer_id"] = customer_id
            callback_context.state["original_request"] = user_text

            return _force_auth_response(
                f"Your session is not verified for {customer_id}. Please authenticate first."
            )

        callback_context.state["auth_required"] = False

    return None


def after_model_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> Optional[LlmResponse]:
    """Record token usage, cost, latency, and optionally prompt/response content."""

    # 1. Latency -----------------------------------------------------------
    start_ns = callback_context.state.get(_START_KEY, None)
    if start_ns is not None:
        latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
    else:
        latency_ms = 0.0

    # 2. Token usage -------------------------------------------------------
    usage = getattr(llm_response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", 0) or 0
    output_tokens = getattr(usage, "candidates_token_count", 0) or 0
    total_tokens = input_tokens + output_tokens

    # 3. Cost --------------------------------------------------------------
    agent_name = getattr(callback_context, "agent_name", None)
    if not agent_name:
        agent_name = getattr(getattr(callback_context, "agent", None), "name", "bank_agent") or "bank_agent"

    model_name = getattr(
        getattr(callback_context, "agent", None), "model", "gemini-2.5-flash"
    ) or "gemini-2.5-flash"
    inp_price, out_price = get_pricing(model_name)
    cost_usd = (input_tokens * inp_price + output_tokens * out_price) / 1_000_000

    # 4. Content previews --------------------------------------------------
    prompt_preview: str | None = None
    response_preview: str | None = None
    if LOG_LLM_CONTENT:
        prompt_preview = callback_context.state.get("_obs_last_prompt", None)
        response_preview = _extract_response_text(llm_response)

    # 5. Session ID --------------------------------------------------------
    session_id = _session_id_from_ctx(callback_context)

    # 6. Record ------------------------------------------------------------
    rec = LlmCallRecord(
        timestamp=time.time(),
        session_id=session_id,
        model=model_name,
        agent_name=agent_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        prompt_preview=prompt_preview,
        response_preview=response_preview,
    )
    store.record_llm_call(rec)

    # 7. Log ---------------------------------------------------------------
    logger.info(
        "LLM call: agent=%s model=%s in=%d out=%d total=%d cost=$%.6f latency=%.1fms session=%s",
        agent_name, model_name, input_tokens, output_tokens, total_tokens, cost_usd, latency_ms, session_id,
    )

    # 8. OTEL span attributes ----------------------------------------------
    if _tracer is not None:
        span = otel_trace.get_current_span()
        if span and span.is_recording():
            span.set_attribute("llm.session_id", session_id)
            span.set_attribute("llm.agent_name", agent_name)
            span.set_attribute("llm.model", model_name)
            span.set_attribute("llm.input_tokens", input_tokens)
            span.set_attribute("llm.output_tokens", output_tokens)
            span.set_attribute("llm.total_tokens", total_tokens)
            span.set_attribute("llm.cost_usd", cost_usd)
            span.set_attribute("llm.latency_ms", latency_ms)

    return None
