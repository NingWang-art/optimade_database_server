import argparse
import logging
import json
from typing import List, Optional, TypedDict, Literal
from pathlib import Path
from datetime import datetime
import hashlib

from optimade.client import OptimadeClient
from dp.agent.server import CalculationMCPServer

from utils import save_structures  # must accept (results, output_folder, max_results, as_cif)

# === CONFIG ===
BASE_OUTPUT_DIR = Path("materials_data")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_PROVIDERS = {
    "alexandria", "cmr", "mp", "mpds", "nmd",
    "odbx", "omdb", "oqmd", "jarvis"
}

# === ARG PARSING ===
def parse_args():
    parser = argparse.ArgumentParser(description="OPTIMADE Materials Data MCP Server (raw filter mode)")
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
Format = Literal["cif", "json"]

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

# === TOOL: raw filter fetch ===
@mcp.tool()
def fetch_structures_with_filter(
    filter: str,
    as_format: Format = "cif",
    max_results_per_provider: int = 2,
    providers: Optional[List[str]] = None,
) -> FetchResult:
    """
    Fetch structures using a RAW OPTIMADE filter string (elements-only for first try).

    Parameters
    ----------
    filter : str
        An OPTIMADE filter expression (use elements-only now). Examples:
        - elements HAS ALL "Al","O","Mg"
        - elements HAS ANY "Al","O"
        - elements HAS ONLY "Si","O"
    as_format : {"cif","json"}, optional
        Output format (default: "cif").
    max_results_per_provider : int, optional
        Max results per provider (default: 2).
    providers : list[str], optional
        Provider keys to query. Uses default set if omitted:
        {"mp","oqmd","jarvis","nmd","mpds","cmr","alexandria","omdb","odbx"}.

    Returns
    -------
    FetchResult
        {
          "output_dir": <Path>,
          "files": [<saved files>],
          "providers_used": [<providers_seen>],
          "filter": "<the filter you sent>",
          "warnings": [<messages>]
        }
    """
    filt = (filter or "").strip()
    if not filt:
        msg = "[raw] empty filter string"
        logging.error(msg)
        return {"output_dir": Path(), "files": [], "providers_used": [], "filter": "", "warnings": [msg]}

    used_providers = set(providers) if providers else DEFAULT_PROVIDERS
    logging.info(f"[raw] providers={used_providers} filter={filt}")

    try:
        client = OptimadeClient(
            include_providers=used_providers,
            max_results_per_provider=max_results_per_provider
        )
        results = client.get(filter=filt)
    except Exception as e:
        msg = f"[raw] fetch failed: {e}"
        logging.error(msg)
        return {
            "output_dir": Path(),
            "files": [],
            "providers_used": sorted(list(used_providers)),
            "filter": filt,
            "warnings": [msg],
        }

    # timestamped folder + short hash of filter for traceability
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short = hashlib.sha1(filt.encode("utf-8")).hexdigest()[:8]
    out_folder = BASE_OUTPUT_DIR / f"rawfilter_{ts}_{short}"

    files, warns, providers_seen = save_structures(
        results,
        out_folder,
        max_results_per_provider,
        as_cif=(as_format == "cif"),
    )

    # manifest (handy for downstream)
    manifest = {
        "filter": filt,
        "providers_requested": sorted(list(used_providers)),
        "providers_seen": providers_seen,
        "files": files,
        "warnings": warns,
        "format": as_format,
        "max_results_per_provider": max_results_per_provider,
    }
    (out_folder / "summary.json").write_text(json.dumps(manifest, indent=2))

    return {
        "output_dir": out_folder,
        "files": files,
        "providers_used": sorted(list(set(providers_seen))),
        "filter": filt,
        "warnings": warns,
    }

# === RUN MCP SERVER ===
if __name__ == "__main__":
    logging.info("Starting Optimade MCP Server (raw filter mode)…")
    mcp.run(transport="sse")