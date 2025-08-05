import argparse
import json
import os
from typing import List

from optimade.client import OptimadeClient
from optimade.adapters.structures import Structure
import jmespath
from pymatgen.core import Composition


# === CONFIG ===
DATA_DIR = "materials_data"
os.makedirs(DATA_DIR, exist_ok=True)


# === UTIL FUNCTION ===
def hill_formula_filter(formula: str) -> str:
    """
    Converts a chemical formula to Hill notation for OPTIMADE filtering.
    Example: "TiO2" → 'chemical_formula_reduced="O2Ti"'
    "O2Ti" → 'chemical_formula_reduced="O2Ti"'
    "SiO2" → 'chemical_formula_reduced="O2Si"'
    "ZrO" → 'chemical_formula_reduced="OZr"'
    """
    hill_formula = Composition(formula).hill_formula.replace(' ', '')
    return f'chemical_formula_reduced="{hill_formula}"'


# === MCP TOOL 1 ===
def fetch_structures_by_formula(formula: str, max_results: int = 2, as_cif: bool = True) -> List[str]:
    """
    Fetch structures from OPTIMADE by chemical formula and store them as CIF files or raw JSON.

    Args:
        formula: Chemical formula string, e.g. "TiO2"
        max_results: Maximum number of structures to retrieve (default: 2)
        as_cif: Whether to convert and save as CIF (True) or raw structure JSON (False)

    Returns:
        List of file paths saved
    """
    filter_str = hill_formula_filter(formula)
    client = OptimadeClient(include_providers={"mp"}, max_results_per_provider=max_results)
    results = client.get(filter=filter_str)

    try:
        structure_data_list = jmespath.search("structures.*.*.data", results)[0][0]
    except Exception as e:
        return [f"Error extracting data: {str(e)}"]

    saved_paths = []
    n_final_data = min(len(structure_data_list), max_results)
    for i, structure_data in enumerate(structure_data_list[:n_final_data]):
        try:
            suffix = "cif" if as_cif else "json"
            file_name = f"{formula.replace(' ', '_')}_{i}.{suffix}"
            file_path = os.path.join(DATA_DIR, file_name)
            with open(file_path, "w") as f:
                if as_cif:
                    f.write(Structure(structure_data).convert('cif'))
                else:
                    json.dump(structure_data, f, indent=2)
            saved_paths.append(file_path)
        except Exception as e:
            saved_paths.append(f"Failed to save structure {i}: {str(e)}")

    return saved_paths


# === MCP TOOL 2 ===
def fetch_structures_by_elements(elements: List[str], max_results: int = 2, as_cif: bool = True) -> List[str]:
    """
    Fetch structures from OPTIMADE by a list of elements.

    Args:
        elements: List of element symbols (e.g. ["Si", "O"], ["Si", "O", "Al"])
        max_results: Max number of structures per provider (default: 2)
        as_cif: Whether to convert and save as CIF (True) or raw structure JSON (False)

    Returns:
        List of file paths saved
    """
    element_filter = 'elements HAS ALL ' + ', '.join(f'"{e}"' for e in elements)
    client = OptimadeClient(include_providers={"mp"}, max_results_per_provider=max_results)
    results = client.get(filter=element_filter)

    try:
        structure_data_list = jmespath.search("structures.*.*.data", results)[0][0]
    except Exception as e:
        return [f"Error extracting data: {str(e)}"]

    saved_paths = []
    n_final_data = min(len(structure_data_list), max_results)
    for i, structure_data in enumerate(structure_data_list[:n_final_data]):
        try:
            suffix = "cif" if as_cif else "json"
            file_name = f"{'_'.join(elements)}_{i}.{suffix}"
            file_path = os.path.join(DATA_DIR, file_name)
            with open(file_path, "w") as f:
                if as_cif:
                    f.write(Structure(structure_data).convert('cif'))
                else:
                    json.dump(structure_data, f, indent=2)
            saved_paths.append(file_path)
        except Exception as e:
            saved_paths.append(f"Failed to save structure {i}: {str(e)}")

    return saved_paths

print(fetch_structures_by_formula(formula='O3Al2', max_results=3, as_cif=False))
print(fetch_structures_by_elements(elements=["O", "Al"], max_results=2, as_cif=True))
