import argparse
import logging
import json
from typing import List, Optional, TypedDict, Literal, Tuple, Dict
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ValidationError
from optimade.client import OptimadeClient
from optimade.adapters.structures import Structure

from dp.agent.server import CalculationMCPServer
from utils import *

# If you have hill_formula_filter etc., we don't use them here (elements-only test)

# === CONFIG ===
BASE_OUTPUT_DIR = Path("materials_data")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_PROVIDERS = {
    "alexandria", "cmr", "mp", "mpds", "nmd",
    "odbx", "omdb", "oqmd", "jarvis"
}

# === ARG PARSING ===
def parse_args():
    parser = argparse.ArgumentParser(description="OPTIMADE Materials Data MCP Server (Elements-only test)")
    parser.add_argument('--port', type=int, default=50001, help='Server port (default: 50001)')
    parser.add_argument('--host', default='0.0.0.0', help='Server host (default: 0.0.0.0)')
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging level (default: INFO)')
    try:
        return parser.parse_args()
    except SystemExit:
        class Args:
            port = 50001
            host = '0.0.0.0'
            log_level = 'INFO'
        return Args()

# === RESULT TYPE ===
class FetchResult(TypedDict):
    output_dir: Path
    files: List[str]
    providers_used: List[str]
    filter: str
    warnings: List[str]

# === MCP SERVER ===
args = parse_args()
logging.basicConfig(level=args.log_level)
mcp = CalculationMCPServer("OptimadeServer", port=args.port, host=args.host)

# === Query schema (elements-only) ===
Format = Literal["cif", "json"]

class QueryParams(BaseModel):
    elements_all: Optional[List[str]] = None   # elements HAS ALL
    elements_any: Optional[List[str]] = None   # elements HAS ANY
    elements_only: Optional[List[str]] = None  # elements HAS ONLY

    as_format: Format = "cif"                  # "cif" or "json"
    max_results_per_provider: int = 2
    providers: Optional[List[str]] = None

# === Filter builder (elements-only) ===
def build_filter(q: "QueryParams") -> str:
    parts = []
    if q.elements_all:
        parts.append('elements HAS ALL ' + ', '.join(f'"{e}"' for e in q.elements_all))
    if q.elements_any:
        parts.append('elements HAS ANY ' + ', '.join(f'"{e}"' for e in q.elements_any))
    if q.elements_only:
        parts.append('elements HAS ONLY ' + ', '.join(f'"{e}"' for e in q.elements_only))
    return " AND ".join(parts) if parts else 'elements HAS ANY "Si"'  # harmless default


# === TOOL: elements-only advanced ===
@mcp.tool()
def fetch_structures_advanced(query: dict) -> FetchResult:
    """
    Advanced OPTIMADE fetch (elements-only test).

    Parameters
    ----------
    query : dict
        JSON object with any of:
        {
          "elements_all": ["Al","O","Mg"],   # elements HAS ALL
          "elements_any": ["Si","O"],        # elements HAS ANY
          "elements_only": ["C"],            # elements HAS ONLY
          "as_format": "cif",                # "cif" or "json"
          "max_results_per_provider": 2,     # int
          "providers": ["mp","jarvis"]       # optional, list of provider keys
        }

    Returns
    -------
    FetchResult
        {
          "output_dir": <Path>,
          "files": [<saved files>],
          "providers_used": [<providers>],
          "filter": "<final filter>",
          "warnings": [<messages>]
        }
    """
    # Validate query
    try:
        q = QueryParams(**query)
    except ValidationError as e:
        logging.error(f"[adv] Query validation failed: {e}")
        return {
            "output_dir": Path(),
            "files": [],
            "providers_used": [],
            "filter": "",
            "warnings": [f"validation_error: {e}"],
        }

    # Build filter + providers
    filter_str = build_filter(q)
    used_providers = set(q.providers) if q.providers else DEFAULT_PROVIDERS
    logging.info(f"[adv] providers={used_providers} filter={filter_str}")

    # Execute query
    try:
        client = OptimadeClient(
            include_providers=used_providers,
            max_results_per_provider=q.max_results_per_provider
        )
        results = client.get(filter=filter_str)
    except Exception as e:
        msg = f"[adv] fetch failed: {e}"
        logging.error(msg)
        return {
            "output_dir": Path(),
            "files": [],
            "providers_used": sorted(list(used_providers)),
            "filter": filter_str,
            "warnings": [msg],
        }

    # Save
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_folder = BASE_OUTPUT_DIR / f"elements_query_{ts}"
    files, warns, providers_seen = save_structures(
        results, out_folder, q.max_results_per_provider, as_cif=(q.as_format == "cif")
    )

    return {
        "output_dir": out_folder,
        "files": files,
        "providers_used": sorted(list(set(providers_seen))),
        "filter": filter_str,
        "warnings": warns,
    }

# === RUN MCP SERVER ===
if __name__ == "__main__":
    logging.info("Starting Optimade MCP Server (elements-only)…")
    mcp.run(transport="sse")