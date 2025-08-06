import os
import asyncio
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_session_manager import SseServerParams
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from typing import Any, Dict

from pathlib import Path
from typing import Any, Dict

import nest_asyncio
from dotenv import load_dotenv
from dp.agent.adapter.adk import CalculationMCPToolset
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai import types


load_dotenv()
nest_asyncio.apply()

# Set environment variables if needed
# Global Configuration
BOHRIUM_EXECUTOR = {
    "type": "dispatcher",
    "machine": {
        "batch_type": "Bohrium",
        "context_type": "Bohrium",
        "remote_profile": {
            "email": os.getenv("BOHRIUM_EMAIL"),
            "password": os.getenv("BOHRIUM_PASSWORD"),
            "program_id": int(os.getenv("BOHRIUM_PROJECT_ID")),
            "input_data": {
                "image_name": "registry.dp.tech/dptech/dp/native/prod-19853/dpa-mcp:0.0.0",
                "job_type": "container",
                "platform": "ali",
                "scass_type": "1 * NVIDIA V100_32g"
            }
        }
    }
}
LOCAL_EXECUTOR = {
    "type": "local"
}
BOHRIUM_STORAGE = {
    "type": "bohrium",
    "username": os.getenv("BOHRIUM_EMAIL"),
    "password": os.getenv("BOHRIUM_PASSWORD"),
    "project_id": int(os.getenv("BOHRIUM_PROJECT_ID"))
}

# HTTPS_STORAGE = {
#   "type": "https",
#   "plugin": {
#         "type": "bohrium",
#         "username": os.getenv("BOHRIUM_EMAIL"),
#         "password": os.getenv("BOHRIUM_PASSWORD"),
#         "project_id": int(os.getenv("BOHRIUM_PROJECT_ID"))
#     }
# }

HTTPS_STORAGE = {
  "type": "https",
  "plugin": {
    "type": "bohrium",
    "access_key": os.getenv("BOHRIUM_ACCESS_KEY"),
    "project_id": int(os.getenv("BOHRIUM_PROJECT_ID")),
    "app_key": "agent"
  }
}

server_url = os.getenv("SERVER_URL")


# Initialize MCP tools and agent
mcp_tools = CalculationMCPToolset(
    connection_params=SseServerParams(url=server_url),
    storage=HTTPS_STORAGE,
    executor=LOCAL_EXECUTOR
)


root_agent = LlmAgent(
    model=LiteLlm(model="deepseek/deepseek-chat"),
    name="Optimade_Agent",
    description="An agent specialized in materials data retrieval using OPTIMADE.",
    instruction=(
        "You are an expert in materials science. "
        "Help users retrieve crystal structure data using the OPTIMADE API. "
        "You can search by chemical formula or by element combinations. "
        "Ask users whether they want results as CIF files or full raw structure data. "
        "Limit the number of structures based on user request or default to 2 if not specified. "
        "After retrieving the data, save the results to a directory and return the compressed data folder **as a download link**, "
        "and also include **the individual file links** if available (such as CIF files). "
        "Explain briefly what the data represents and suggest how it can be used in simulations, visualization, or materials analysis."
    ),
    tools=[mcp_tools],
)