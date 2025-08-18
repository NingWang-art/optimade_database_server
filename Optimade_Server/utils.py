import os
import time
import logging
import json
from pathlib import Path
from typing import List, Dict, Iterable, Optional
from optimade.adapters.structures import Structure
from pymatgen.core import Composition
from pymatgen.symmetry.groups import SpaceGroup

import re

from urllib.parse import urlparse
import oss2
from dotenv import load_dotenv
from oss2.credentials import EnvironmentVariableCredentialsProvider

# === LOAD ENV ===
load_dotenv()


DEFAULT_PROVIDERS = {
    # "aflow",
    "alexandria",
    # "aiida",
    # "ccdc",
    # "ccpnc",
    "cmr",
    "cod",
    # "httk",
    # "jarvis",
    "mcloud",
    "mcloudarchive",
    "mp",
    "mpdd",
    "mpds",
    # "mpod",
    "nmd",
    "odbx",
    "omdb",
    "oqmd",
    # "optimade",
    # "optimake",
    # "pcod",
    # "psdi",
    "tcod",
    "twodmatpedia",
}

DEFAULT_SPG_PROVIDERS = {
    "alexandria",
    "cod",
    "mpdd",
    "nmd",
    "odbx",
    "oqmd",
    "tcod",
}

DEFAULT_BG_PROVIDERS = {
    "alexandria",
    "odbx",
    "oqmd",
    "mcloudarchive",
    "twodmatpedia",
}

# === UTILS ===
def hill_formula_filter(formula: str) -> str:
    hill_formula = Composition(formula).hill_formula.replace(' ', '')
    return f'chemical_formula_reduced="{hill_formula}"'


# def upload_file_to_oss(file_path: Path) -> str:
#     """
#     上传文件至 OSS, 返回公开访问链接
#     """
#     auth = oss2.ProviderAuth(EnvironmentVariableCredentialsProvider())
#     endpoint = os.environ["OSS_ENDPOINT"]
#     bucket_name = os.environ["OSS_BUCKET_NAME"]
#     bucket = oss2.Bucket(auth, endpoint, bucket_name)

#     ext = file_path.suffix.lower().lstrip('.')
#     oss_filename = f"{ext}_{file_path.name}_{int(time.time())}.{ext}"
#     oss_path = f"retrosyn/{oss_filename}"

#     with open(file_path, "rb") as f:
#         bucket.put_object(oss_path, f)

#     region = endpoint.split('.')[0].replace("oss-", "")
#     return f"https://{bucket_name}.oss-{region}.aliyuncs.com/{oss_path}"



# === Saver ===
def _provider_name_from_url(url: str) -> str:
    """Turn provider URL into a filesystem-safe name."""
    parsed = urlparse(url)
    netloc = parsed.netloc.replace('.', '_')
    path = parsed.path.strip('/').replace('/', '_')
    name = f"{netloc}_{path}" if path else netloc
    return name.strip('_') or "provider"

def save_structures(results: Dict, output_folder: Path, max_results: int, as_cif: bool):
    """
    Walk OPTIMADE aggregated results and write per-provider files.
    Returns files list, warnings list, providers_seen list.
    """
    output_folder.mkdir(parents=True, exist_ok=True)
    files: List[str] = []
    warnings: List[str] = []
    providers_seen: List[str] = []

    structures_by_filter = results.get("structures", {})
    for _, provider_dict in structures_by_filter.items():
        for provider_url, content in provider_dict.items():
            provider_name = _provider_name_from_url(provider_url)
            providers_seen.append(provider_name)
            data_list = content.get("data", [])
            logging.info(f"[save] {provider_name}: {len(data_list)} candidates")

            for i, structure_data in enumerate(data_list[:max_results]):
                suffix = "cif" if as_cif else "json"
                filename = f"{provider_name}_{i}.{suffix}"
                file_path = output_folder / filename

                try:
                    if as_cif:
                        cif_content = Structure(structure_data).convert('cif')
                        if not cif_content or not cif_content.strip():
                            raise ValueError("CIF content is empty")
                        file_path.write_text(cif_content)
                    else:
                        file_path.write_text(json.dumps(structure_data, indent=2))

                    logging.debug(f"[save] wrote {file_path}")
                    files.append(str(file_path))
                except Exception as e:
                    msg = f"Failed to save structure from {provider_name} #{i}: {e}"
                    logging.warning(msg)
                    warnings.append(msg)

    return files, warnings, providers_seen


def filter_to_tag(filter_str: str, max_len: int = 30) -> str:
    """
    Convert an OPTIMADE filter string into a short, filesystem-safe tag.

    Parameters
    ----------
    filter_str : str
        The original OPTIMADE filter string.
    max_len : int, optional
        Maximum length of the resulting tag (default: 30).

    Returns
    -------
    str
        A short, sanitized tag derived from the filter.
    """
    # Remove surrounding spaces and quotes
    tag = filter_str.strip().replace('"', '').replace("'", "")

    # Replace spaces, commas, and equals with underscores/dashes
    tag = tag.replace(" ", "_").replace(",", "-").replace("=", "")

    # Keep only safe characters: alphanumeric, underscore, dash
    tag = "".join(c for c in tag if c.isalnum() or c in "_-")

    # Limit length
    if len(tag) > max_len:
        tag = tag[:max_len]

    # Fallback if everything gets stripped
    return tag or "filter"



def _hm_symbol_from_number(spg_number: int) -> Optional[str]:
    """Return the short Hermann–Mauguin symbol (e.g. 'Im-3m') for a space-group number."""
    try:
        return SpaceGroup.from_int_number(spg_number).symbol
    except Exception as e:
        logging.warning(f"[spg] cannot map number {spg_number} to H–M symbol: {e}")
        return None

def _to_tcod_format(hm: str) -> str:
    """
    Convert a short Hermann–Mauguin symbol to TCOD spacing.
    Examples:
        'Pm-3m'   -> 'P m -3 m'
        'P4/mmm'  -> 'P 4/m m m'
        'Fd-3m'   -> 'F d -3 m'
    """
    s = hm.strip()
    # 1) Expand groups after '/' → '/m m m', '/mm' → '/m m', '/mc' → '/m c', etc.
    s = re.sub(r'/([A-Za-z]+)', lambda m: '/' + ' '.join(m.group(1)), s)
    # 2) Put spaces between ANY two consecutive letters (F d, P m, …)
    s = re.sub(r'(?<=[A-Za-z])(?=[A-Za-z])', ' ', s)
    # 3) Put spaces between letter↔digit transitions (P4 → P 4, 4m → 4 m)
    s = re.sub(r'(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])', ' ', s)
    # 4) Put a space only *before* the minus (attach '-' to the number): 'm-3' -> 'm -3'
    s = re.sub(r'\s*-\s*(?=\d)', ' -', s)
    # 5) Collapse multiple spaces
    return ' '.join(s.split())

def get_spg_filter_map(spg_number: int, providers: Iterable[str]) -> Dict[str, str]:
    """
    Map provider name → space-group filter clause for that provider.
    Handles alexandria, nmd, mpdd, odbx, oqmd, tcod, cod.
    """
    hm = _hm_symbol_from_number(spg_number)

    name_map = {
        "alexandria": lambda: f"_alexandria_space_group={spg_number}",
        "nmd":        lambda: f"_nmd_dft_spacegroup={spg_number}",
        "mpdd":       lambda: f"_mpdd_spacegroupn={spg_number}",
        "odbx":       lambda: f"_gnome_space_group_it_number={spg_number}",
        "oqmd":       lambda: f'_oqmd_spacegroup="{hm}"' if hm else "",
        "tcod":       lambda: f'_tcod_sg="{_to_tcod_format(hm)}"' if hm else "",
        "cod":        lambda: f'_cod_sg="{_to_tcod_format(hm)}"' if hm else "",
    }

    out: Dict[str, str] = {}
    for p in providers:
        if p in name_map:
            clause = name_map[p]()
            if clause:
                out[p] = clause
    return out


def _range_clause(prop: str, min_bg: Optional[float], max_bg: Optional[float]) -> str:
    """Return OPTIMADE range clause like: prop>=a AND prop<=b (handles open ends)."""
    parts = []
    if min_bg is not None:
        parts.append(f"{prop}>={min_bg}")
    if max_bg is not None:
        parts.append(f"{prop}<={max_bg}")
    return " AND ".join(parts) if parts else ""  # empty means 'no constraint'

def get_bandgap_filter_map(
    min_bg: Optional[float],
    max_bg: Optional[float],
    providers: Optional[Iterable[str]] = None,
) -> Dict[str, str]:
    """
    Map provider name → band-gap clause using provider-specific property names.
    Providers without a known property are omitted.
    If providers is None, uses DEFAULT_BG_PROVIDERS.
    """
    providers = set(providers) if providers else DEFAULT_BG_PROVIDERS

    name_map = {
        "alexandria": "_alexandria_band_gap",
        "odbx": "_gnome_bandgap",             
        "oqmd": "_oqmd_band_gap",
        "mcloudarchive": "_mcloudarchive_band_gap",
        "twodmatpedia": "_twodmatpedia_band_gap",
    }

    out: Dict[str, str] = {}
    for p in providers:
        prop = name_map.get(p)
        if not prop:
            continue
        clause = _range_clause(prop, min_bg, max_bg)
        if clause:
            out[p] = clause
    return out

def build_provider_filters(base: Optional[str], provider_map: Dict[str, str]) -> Dict[str, str]:
    """
    Combine a base OPTIMADE filter with per-provider clauses.

    Parameters
    ----------
    base : str, optional
        Common OPTIMADE filter applied to all providers (can be empty/None).
    provider_map : dict
        {provider: specific_clause} mapping for each provider.

    Returns
    -------
    dict
        {provider: combined_clause}
    """
    b = (base or "").strip()
    return {
        p: f"({b}) AND ({c.strip()})" if b and c.strip() else (b or c.strip())
        for p, c in provider_map.items()
        if c and c.strip()  # skip empty clauses
    }


# output1 = get_spg_filter_map(225, providers=DEFAULT_SPG_PROVIDERS)
# pass