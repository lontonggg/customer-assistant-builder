from google.adk.agents import LlmAgent
from dotenv import load_dotenv

load_dotenv()

root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="customer_agent",
    instruction=(
        "You are a helpful customer engagement assistant. "
        "Answer questions accurately using the provided business knowledge context. "
        "If information is not available in the context, say so clearly."
    ),
)
