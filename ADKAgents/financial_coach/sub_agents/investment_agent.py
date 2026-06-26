import os
from functools import cached_property

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.genai import Client

from ..prompt import INVESTMENT_AGENT_PROMPT
from ..tools.investments import (
    get_portfolio_tool,
    get_allocation_tool,
)


class VertexGemini(Gemini):
    @cached_property
    def api_client(self) -> Client:
        return Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )


investment_agent = Agent(
    name="investment_agent",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="""
        Handles all queries about a customer's investment portfolio.
        Use this agent for:
        - Viewing mutual funds, stocks, ETFs, gold, bonds
        - Checking portfolio returns and current value
        - Analysing asset allocation and diversification
        - Reviewing monthly SIP contributions
        - Rebalancing recommendations based on risk profile
    """,
    instruction=INVESTMENT_AGENT_PROMPT,
    tools=[
        get_portfolio_tool,   # get_investment_portfolio(customer_id)
        get_allocation_tool,  # get_asset_allocation(customer_id)
    ],
)
