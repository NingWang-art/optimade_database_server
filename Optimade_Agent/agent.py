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
    description="An agent specialized in materials data retrieval using the OPTIMADE protocol.",
    instruction=(
        "You are a materials science expert using the OPTIMADE API to retrieve crystal structure data "
        "from public databases.\n\n"
        "Users can search by:\n"
        "- Chemical formula (e.g., `TiO2`)\n"
        "- Element list (e.g., `Mg`, `Al`, `O`)\n\n"
        "Ask users for their preferred format:\n"
        "- CIF (standard crystallographic format)\n"
        "- JSON (raw structure data)\n\n"
        "Users can specify the number of results (default: 2) and optionally choose which databases to query.\n"
        "Available databases:\n"
        "- `mp`, `oqmd`, `jarvis`, `nmd`, `mpds`, `cmr`, `alexandria`, `omdb`, `odbx`\n"
        "(These are also used by default if none are specified.)\n\n"
        "Save results in a timestamped folder, return a download link to the folder, and include direct links "
        "to individual files when possible.\n\n"
        "Briefly explain what the data represents and how it can be used in simulations, visualization, or materials analysis."
    ),
    tools=[mcp_tools],
)