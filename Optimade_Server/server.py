import argparse
import logging
from typing import List, Optional, TypedDict
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

from optimade.client import OptimadeClient
from optimade.adapters.structures import Structure

from dp.agent.server import CalculationMCPServer

from utils import *

# === CONFIG ===
BASE_OUTPUT_DIR = Path("materials_data")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_PROVIDERS = {
    "alexandria", "cmr", "mp", "mpds", "nmd",
    "odbx", "omdb", "oqmd", "jarvis"
}


# === ARG PARSING ===
def parse_args():
    parser = argparse.ArgumentParser(description="OPTIMADE Materials Data MCP Server")
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


# === MCP SERVER ===
args = parse_args()
logging.basicConfig(level=args.log_level)
mcp = CalculationMCPServer("OptimadeServer", port=args.port, host=args.host)


# === TOOL 1 ===
@mcp.tool()
def fetch_structures_by_formula(
    formula: str,
    max_results: int = 2,
    as_cif: bool = True,
    providers: Optional[List[str]] = None
) -> FetchResult:
    """
    Fetch structures from OPTIMADE databases by chemical formula.

    Parameters
    ----------
    formula : str
        The chemical formula to search for (e.g., "TiO2").
    max_results : int, optional
        Maximum number of structures to fetch per provider.
    as_cif : bool, optional
        Whether to save structures as CIF files. If False, saves as JSON.
    providers : list of str, optional
        Specific providers to query. If None, uses all default providers.

    Returns
    -------
    FetchResult
        A dictionary with the output directory path.
    """
    filter_str = hill_formula_filter(formula)
    used_providers = set(providers) if providers else DEFAULT_PROVIDERS
    logging.info(f"Fetching structures for formula '{formula}' using providers: {used_providers}")
    logging.debug(f"Using filter string: {filter_str}")

    try:
        client = OptimadeClient(include_providers=used_providers, max_results_per_provider=max_results)
        results = client.get(filter=filter_str)
    except Exception as e:
        logging.error(f"Failed to fetch structures by formula '{formula}': {e}")
        return {"output_dir": Path()}

    output_folder = BASE_OUTPUT_DIR / f"formula_{formula}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    save_structures(results, output_folder, max_results, as_cif)

    return {"output_dir": output_folder}


# === TOOL 2 ===
@mcp.tool()
def fetch_structures_by_elements(
    elements: List[str],
    max_results: int = 2,
    as_cif: bool = True,
    providers: Optional[List[str]] = None
) -> FetchResult:
    """
    Fetch structures from OPTIMADE databases by a list of elements.

    Parameters
    ----------
    elements : list of str
        Elements to include in search (e.g., ["Mg", "O", "Al"]).
    max_results : int, optional
        Max number of structures to fetch per provider.
    as_cif : bool, optional
        Save results as CIF (True) or JSON (False).
    providers : list of str, optional
        Specific OPTIMADE providers to query. Uses default if not provided.

    Returns
    -------
    FetchResult
        A dictionary with the output directory path.
    """
    element_filter = 'elements HAS ALL ' + ', '.join(f'"{e}"' for e in elements)
    used_providers = set(providers) if providers else DEFAULT_PROVIDERS
    logging.info(f"Fetching structures for elements {elements} using providers: {used_providers}")
    logging.debug(f"Using filter string: {element_filter}")

    try:
        client = OptimadeClient(include_providers=used_providers, max_results_per_provider=max_results)
        results = client.get(filter=element_filter)
    except Exception as e:
        logging.error(f"Failed to fetch structures for elements {elements}: {e}")
        return {"output_dir": Path()}

    folder_name = "elements_" + "_".join(elements) + "_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    output_folder = BASE_OUTPUT_DIR / folder_name
    save_structures(results, output_folder, max_results, as_cif)

    return {"output_dir": output_folder}


# === RUN MCP SERVER ===
if __name__ == "__main__":
    logging.info("Starting Optimade MCP Server...")
    mcp.run(transport="sse")