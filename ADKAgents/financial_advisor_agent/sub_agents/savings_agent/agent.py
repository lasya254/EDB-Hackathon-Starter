import os
from functools import cached_property
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.genai import Client
from .tools import get_customer_info, get_available_bonds, calculate_returns, compare_bonds
from .prompt import SAVINGS_AGENT_INSTRUCTION

load_dotenv()

class VertexGemini(Gemini):
    @cached_property
    def api_client(self) -> Client:
        return Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )

root_agent = Agent(
    name="savings_agent",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="Savings relationship pricing agent for bond investments.",
    instruction=SAVINGS_AGENT_INSTRUCTION,
    tools=[get_customer_info, get_available_bonds, calculate_returns, compare_bonds],
)