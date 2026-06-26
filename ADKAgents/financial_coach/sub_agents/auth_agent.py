import os
from functools import cached_property

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.genai import Client

from ..prompt import AUTH_AGENT_PROMPT
from ..tools.auth import (
    initiate_auth,
    verify_auth,
    check_session,
)


class VertexGemini(Gemini):
    @cached_property
    def api_client(self) -> Client:
        return Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )


auth_agent = Agent(
    name="auth_agent",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="""
        Handles customer authentication before any sensitive financial
        information is shown.
        Use this agent for:
        - Verifying customer identity for a customer_id
        - Asking the authentication challenge
        - Validating the user's answer
        - Confirming whether an auth session is still valid
    """,
    instruction=AUTH_AGENT_PROMPT,
    tools=[
        initiate_auth,   # initiate_auth(customer_id)
        verify_auth,     # verify_auth(session_id, customer_id, answer)
        check_session,   # check_session(session_id, customer_id)
    ],
)
