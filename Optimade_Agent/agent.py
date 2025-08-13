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
    description="Retrieves crystal structures from OPTIMADE databases using a RAW filter string.",
    instruction=(
        "Use the OPTIMADE API with a RAW filter string. You must supply:\n"
        "- filter: an OPTIMADE filter string\n"
        "- as_format: \"cif\" (default) or \"json\"\n"
        "- max_results_per_provider: integer (default 2)\n"
        "- providers: optional list (default: aflow, alexandria, cmr, cod, jarvis, matcloud, matterverse, mcloud, mcloudarchive, mp, mpdd, mpds, mpod, nmd, odbx, omdb, oqmd, tcod, twodmatpedia)\n\n"

        "=== OPTIMADE FILTER SYNTAX QUICK GUIDE ===\n"
        "• String equality: chemical_formula_reduced=\"O2Si\"\n"
        "• Substring: chemical_formula_descriptive CONTAINS \"H2O\"\n"
        "• Lists: elements HAS ALL \"Al\",\"O\",\"Mg\" | HAS ANY | HAS ONLY\n"
        "• Numbers: nelements=3, nelements>=2 AND nelements<=7\n"
        "• Logic: AND, OR, NOT (use parentheses to group)\n"
        "• Examples of grouping: (A AND B) OR (C AND NOT D)\n\n"

        "=== SUPPORTED PROPERTIES (use exactly as shown) ===\n"
        "- elements (list[str]): e.g., elements HAS ALL \"Si\",\"O\"; can combine with nelements or LENGTH\n"
        "- nelements (int): e.g., nelements=3, nelements>=2 AND nelements<=7\n"
        "- chemical_formula_reduced (str): exact reduced formula in alphabetical order, e.g., \"H2NaO\", \"O2Si\"\n"
        "- chemical_formula_descriptive (str): free-form; supports CONTAINS and exact equality\n"
        "- chemical_formula_anonymous (str): exact, e.g., \"A2B\"\n"
        "Tip: To enforce EXACT element set, prefer: elements HAS ALL \"A\",\"B\",\"C\" AND nelements=3\n\n"

        "=== RELIABILITY NOTES ===\n"
        "- Some providers may not support all properties equally (e.g., descriptive CONTAINS). If a query fails, try a simpler filter.\n"
        "- Keep element symbols properly capitalized and strings double-quoted.\n\n"

        "=== EXAMPLES (USER ASK → TOOL ARGS) ===\n"
        "1) 同时包含 Al、O、Mg（且只这三种元素），每库最多 3 个，CIF：\n"
        "   filter: elements HAS ALL \"Al\",\"O\",\"Mg\" AND nelements=3\n"
        "   as_format: \"cif\"; max_results_per_provider: 3\n\n"
        "2) 含有 Al 或 O 任意其一，每库 1 个，JSON：\n"
        "   filter: elements HAS ANY \"Al\",\"O\"\n"
        "   as_format: \"json\"; max_results_per_provider: 1\n\n"
        "3) 只包含 Si 与 O 的结构（不含其他元素），从 MP 和 JARVIS 各取 1 个，CIF：\n"
        "   filter: elements HAS ONLY \"Si\",\"O\"\n"
        "   providers: [\"mp\",\"jarvis\"]; as_format: \"cif\"; max_results_per_provider: 1\n\n"
        "4) 精确配方为 O2Si（Reduced），默认库，CIF：\n"
        "   filter: chemical_formula_reduced=\"O2Si\"\n"
        "   as_format: \"cif\"\n\n"
        "5) 配方描述包含 H2O（自由格式），JSON：\n"
        "   filter: chemical_formula_descriptive CONTAINS \"H2O\"\n"
        "   as_format: \"json\"\n\n"
        "6) 匿名配方为 A2B，且排除含 Na 的：\n"
        "   filter: chemical_formula_anonymous=\"A2B\" AND NOT (elements HAS ANY \"Na\")\n\n"
        "7) 逻辑组合：含 Si 且 (含 O 或 含 Al)，但不含 H：\n"
        "   filter: elements HAS ANY \"Si\" AND (elements HAS ANY \"O\" OR elements HAS ANY \"Al\") AND NOT (elements HAS ANY \"H\")\n\n"

        "When you answer users, explain briefly what you searched for, and return the download link (and file list if available)."
    ),
    tools=[mcp_tools],  # make sure this exposes fetch_structures_with_filter(filter, as_format, max_results_per_provider, providers)
)

# 找3个包含si o， 且含有四种元素的，不能同时含有铁铝，的材料，从alexandria, cmr, nmd，oqmd，jarvis，omdb中查找
# 找到一些A2b3C4的材料，不能含有 Fe，F，CI，H元素，要含有铝或者镁或者钠，我要全部信息
# 我想要一个Tio2结构，从mpds, cmr, alexandria, omdb, odbx里面找