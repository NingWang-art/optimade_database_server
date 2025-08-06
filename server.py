import argparse
import logging
import json
import os
from typing import List, TypedDict
from pathlib import Path
from datetime import datetime

from optimade.client import OptimadeClient
from optimade.adapters.structures import Structure
import jmespath
from pymatgen.core import Composition

from dp.agent.server import CalculationMCPServer

# === CONFIG ===
BASE_OUTPUT_DIR = Path("materials_data")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
        # In ADK dev UI fallback
        class Args:
            port = 50001
            host = '0.0.0.0'
            log_level = 'INFO'
        return Args()


# === RESULT TYPE ===
class FetchResult(TypedDict):
    output_dir: Path
    message: str


# === MCP SERVER ===
args = parse_args()
logging.basicConfig(level=args.log_level)
mcp = CalculationMCPServer("OptimadeServer", port=args.port, host=args.host)


# === UTILS ===
def hill_formula_filter(formula: str) -> str:
    hill_formula = Composition(formula).hill_formula.replace(' ', '')
    return f'chemical_formula_reduced="{hill_formula}"'


# === TOOL 1 ===
@mcp.tool()
def fetch_structures_by_formula(formula: str, max_results: int = 2, as_cif: bool = True) -> FetchResult:
    """
    Fetch structures by formula and save as CIF or JSON. Returns output folder path and message.
    """
    filter_str = hill_formula_filter(formula)
    client = OptimadeClient(include_providers={"mp"}, max_results_per_provider=max_results)
    results = client.get(filter=filter_str)

    try:
        structure_data_list = jmespath.search("structures.*.*.data", results)[0][0]
    except Exception as e:
        return {
            "output_dir": Path(),
            "message": f"Error extracting data: {str(e)}"
        }

    output_folder = BASE_OUTPUT_DIR / f"{formula}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_folder.mkdir(parents=True, exist_ok=True)

    for i, structure_data in enumerate(structure_data_list[:max_results]):
        try:
            suffix = "cif" if as_cif else "json"
            file_path = output_folder / f"{formula.replace(' ', '_')}_{i}.{suffix}"
            with open(file_path, "w") as f:
                if as_cif:
                    f.write(Structure(structure_data).convert('cif'))
                else:
                    json.dump(structure_data, f, indent=2)
        except Exception as e:
            logging.warning(f"Failed to save structure {i}: {str(e)}")

    return {
        "output_dir": output_folder,
        "message": f"Saved structures to folder: {output_folder}"
    }


# === TOOL 2 ===
@mcp.tool()
def fetch_structures_by_elements(elements: List[str], max_results: int = 2, as_cif: bool = True) -> FetchResult:
    """
    Fetch structures by element list and save as CIF or JSON. Returns output folder path and message.
    """
    element_filter = 'elements HAS ALL ' + ', '.join(f'"{e}"' for e in elements)
    client = OptimadeClient(include_providers={"mp"}, max_results_per_provider=max_results)
    results = client.get(filter=element_filter)

    try:
        structure_data_list = jmespath.search("structures.*.*.data", results)[0][0]
    except Exception as e:
        return {
            "output_dir": Path(),
            "message": f"Error extracting data: {str(e)}"
        }

    folder_name = "_".join(elements) + "_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    output_folder = BASE_OUTPUT_DIR / folder_name
    output_folder.mkdir(parents=True, exist_ok=True)

    for i, structure_data in enumerate(structure_data_list[:max_results]):
        try:
            suffix = "cif" if as_cif else "json"
            file_path = output_folder / f"{'_'.join(elements)}_{i}.{suffix}"
            with open(file_path, "w") as f:
                if as_cif:
                    f.write(Structure(structure_data).convert('cif'))
                else:
                    json.dump(structure_data, f, indent=2)
        except Exception as e:
            logging.warning(f"Failed to save structure {i}: {str(e)}")

    return {
        "output_dir": output_folder,
        "message": f"Saved structures to folder: {output_folder}"
    }


# === RUN MCP SERVER ===
if __name__ == "__main__":
    logging.info("Starting Optimade MCP Server...")
    mcp.run(transport="sse")