import os
from functools import cached_property
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools import agent_tool
from google.genai import Client

# Import the existing specialist agents directly
from .sub_agents.bank_agent.agent import root_agent as bank_agent
from .sub_agents.savings_agent.agent import root_agent as savings_agent

from .prompt import FINANCIAL_ADVISOR_INSTRUCTION

load_dotenv()


class VertexGemini(Gemini):
    """Gemini model that unconditionally uses Vertex AI (ADC) instead of an API key."""
    @cached_property
    def api_client(self) -> Client:
        return Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )


# Wrap each specialist agent as a callable tool
bank_tool = agent_tool.AgentTool(agent=bank_agent)
savings_tool = agent_tool.AgentTool(agent=savings_agent)

root_agent = Agent(
    name="financial_advisor_agent",
    model=VertexGemini(model="gemini-2.5-flash"),
    description=(
        "A financial advisor coordinator that consults a banking specialist "
        "and a savings specialist, then merges their advice into one answer."
    ),
    instruction=FINANCIAL_ADVISOR_INSTRUCTION,
    tools=[bank_tool, savings_tool],
)