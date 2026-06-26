import os
from functools import cached_property

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.genai import Client

from ..prompt import FD_AGENT_PROMPT
from ..tools.fixed_deposits import (
    get_fds_tool,
)


class VertexGemini(Gemini):
    @cached_property
    def api_client(self) -> Client:
        return Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )


fd_agent = Agent(
    name="fd_agent",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="""
        Handles all queries about a customer's fixed deposits.
        Use this agent for:
        - Listing all active FDs with principal and maturity value
        - Checking interest rates and expected returns
        - Identifying FDs maturing within the next 90 days
        - Renewal and reinvestment suggestions
    """,
    instruction=FD_AGENT_PROMPT,
    tools=[
        get_fds_tool,   # get_fixed_deposits(customer_id)
    ],
)
