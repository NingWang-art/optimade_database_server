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
    description="An agent that retrieves crystal structures from OPTIMADE databases.",
    instruction=(
        "Use the OPTIMADE API to fetch crystal structures via a RAW filter string (elements-only for now). "
        "Do NOT mix in formula, LENGTH, or nperiodic_dimensions at this stage.\n\n"
        "Tool parameters to provide:\n"
        "- filter: an OPTIMADE filter using elements-only operators\n"
        "  • HAS ALL   -> elements HAS ALL \"Al\",\"O\",\"Mg\"\n"
        "  • HAS ANY   -> elements HAS ANY \"Al\",\"O\"\n"
        "  • HAS ONLY  -> elements HAS ONLY \"Si\",\"O\"\n"
        "- as_format: \"cif\" (default) or \"json\"\n"
        "- max_results_per_provider: integer (default 2)\n"
        "- providers: optional list (default set: `mp`, `oqmd`, `jarvis`, `nmd`, `mpds`, `cmr`, `alexandria`, `omdb`, `odbx`)\n\n"
        "Response expectations:\n"
        "- Results are saved in a timestamped folder; return the download link (and list individual files when available).\n"
        "- Briefly explain what the data contains and typical uses (e.g., visualization with VESTA, DFT inputs).\n\n"
        "Example queries (what the user might say):\n"
        "1) “查找 3 个同时包含 Al、O、Mg 的结构，CIF 格式。”\n"
        "   -> filter: elements HAS ALL \"Al\",\"O\",\"Mg\"; as_format: \"cif\"; max_results_per_provider: 3\n\n"
        "2) “查找含有 Al 或 O 的任意结构，每个数据库 1 个，JSON 格式。”\n"
        "   -> filter: elements HAS ANY \"Al\",\"O\"; as_format: \"json\"; max_results_per_provider: 1\n\n"
        "3) “查找只包含 Si 和 O 的结构（不含其他元素），从 MP 和 JARVIS 各取 1 个。”\n"
        "   -> filter: elements HAS ONLY \"Si\",\"O\"; as_format: \"cif\"; max_results_per_provider: 1; providers: [\"mp\",\"jarvis\"]\n"
    ),
    tools=[mcp_tools],
)