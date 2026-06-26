import os
from functools import cached_property

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.genai import Client

from .observability import (
    after_model_callback,
    before_model_callback,
    setup_observability,
)
from .prompt import ROOT_AGENT_PROMPT
from .sub_agents import (
    customer_context_agent,
    spending_agent,
    investment_agent,
    debt_agent,
    fd_agent,
    insurance_agent,
    financial_score_agent,
)

load_dotenv()


class VertexGemini(Gemini):
    """Gemini on Vertex AI using Application Default Credentials."""

    @cached_property
    def api_client(self) -> Client:
        return Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )


setup_observability()

root_agent = Agent(
    name="financial_coach",
    model=VertexGemini(model="gemini-2.5-flash"),
    description=(
        "Master financial coach that delegates to specialist agents for "
        "customer context, spending, investments, debt, fixed deposits, "
        "insurance, and financial score."
    ),
    instruction=ROOT_AGENT_PROMPT,
    tools=[],
    sub_agents=[
        customer_context_agent,
        spending_agent,
        investment_agent,
        debt_agent,
        fd_agent,
        insurance_agent,
        financial_score_agent,
    ],
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)
