import os
from functools import cached_property

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.genai import Client

from ..prompt import CUSTOMER_CONTEXT_AGENT_PROMPT
from ..tools.customer_context import (
    get_profile_tool,
    get_accounts_tool,
    get_summary_tool,
)


class VertexGemini(Gemini):
    @cached_property
    def api_client(self) -> Client:
        return Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )


customer_context_agent = Agent(
    name="customer_context_agent",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="""
        Handles all queries about a customer's bank accounts,
        balances, and recent transaction history.
        Use this agent for:
        - Fetching customer profile and account details
        - Checking account balances by product type
        - Summarising recent credits, debits, and cashflow
    """,
    instruction=CUSTOMER_CONTEXT_AGENT_PROMPT,
    tools=[
        get_profile_tool,    # get_customer_profile(customer_id)
        get_accounts_tool,   # get_customer_accounts(customer_id)
        get_summary_tool,    # get_customer_summary(customer_id)
    ],
)
