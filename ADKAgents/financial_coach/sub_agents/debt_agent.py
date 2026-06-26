import os
from functools import cached_property

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.genai import Client

from ..prompt import DEBT_AGENT_PROMPT
from ..tools.loans import (
    get_loans_tool,
    get_debt_metrics_tool,
)
from ..tools.credit_cards import (
    get_credit_cards_tool,
)


class VertexGemini(Gemini):
    @cached_property
    def api_client(self) -> Client:
        return Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )


debt_agent = Agent(
    name="debt_agent",
    model=VertexGemini(model="gemini-2.5-flash"),
    description="""
        Handles all queries about a customer's loans and credit cards.
        Use this agent for:
        - Viewing outstanding loans (home, car, personal, education)
        - Checking EMI burden and remaining tenure
        - Calculating debt-to-income (DTI) ratio
        - Credit card balances and utilization percentage
        - Upcoming payment due dates and minimum due alerts
        - Debt repayment strategies (avalanche / snowball)
    """,
    instruction=DEBT_AGENT_PROMPT,
    tools=[
        get_loans_tool,          # get_all_loans(customer_id)
        get_debt_metrics_tool,   # get_debt_metrics(customer_id, monthly_income)
        get_credit_cards_tool,   # get_credit_cards(customer_id)
    ],
)
