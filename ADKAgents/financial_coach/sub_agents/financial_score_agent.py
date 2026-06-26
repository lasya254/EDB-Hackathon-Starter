import os
from functools import cached_property

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.genai import Client

from ..prompt import FINANCIAL_SCORE_AGENT_PROMPT
from ..tools.financial_score import calculate_financial_score_tool


class VertexGemini(Gemini):
    @cached_property
    def api_client(self) -> Client:
        return Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )


financial_score_agent = Agent(
    name="financial_score_agent",
    model=VertexGemini(model="gemini-2.5-flash"),
    description=(
        "Calculates a financial health score percentage for a customer "
        "based on savings, spending, debt, credit utilization, investments, "
        "liquidity, and insurance coverage."
    ),
    instruction=FINANCIAL_SCORE_AGENT_PROMPT,
    tools=[calculate_financial_score_tool],
)
