import os
from functools import cached_property

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.genai import Client

from ..prompt import SPENDING_AGENT_PROMPT
from ..tools.spending import (
    get_monthly_spending_breakdown_tool,
    get_spending_trends_tool,
    get_top_merchants_tool,
    get_recurring_expenses_tool,
    calculate_savings_rate_tool,
)


class VertexGemini(Gemini):
    @cached_property
    def api_client(self) -> Client:
        return Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )


spending_agent = Agent(
    name="spending_agent",
    model=VertexGemini(model="gemini-2.5-flash"),
    description=(
        "Handles spending analysis, category-level expense patterns, "
        "merchant concentration, recurring expenses, monthly trends, "
        "and savings-rate analysis."
    ),
    instruction=SPENDING_AGENT_PROMPT,
    tools=[
        get_monthly_spending_breakdown_tool,
        get_spending_trends_tool,
        get_top_merchants_tool,
        get_recurring_expenses_tool,
        calculate_savings_rate_tool,
    ],
)
