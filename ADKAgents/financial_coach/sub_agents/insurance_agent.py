import os
from functools import cached_property

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.genai import Client

from ..prompt import INSURANCE_AGENT_PROMPT
from ..tools.insurance import (
    get_policies_tool,
    get_adequacy_tool,
)


class VertexGemini(Gemini):
    @cached_property
    def api_client(self) -> Client:
        return Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )


insurance_agent = Agent(
    name="insurance_agent",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="""
        Handles all queries about a customer's insurance policies.
        Use this agent for:
        - Listing active policies (term life, health, motor, home)
        - Checking premium amounts and renewal dates
        - Identifying policies expiring within 60 days
        - Analysing life cover and health cover adequacy
        - Calculating coverage gaps vs recommended amounts
    """,
    instruction=INSURANCE_AGENT_PROMPT,
    tools=[
        get_policies_tool,   # get_insurance_policies(customer_id)
        get_adequacy_tool,   # check_insurance_adequacy(...)
    ],
)
