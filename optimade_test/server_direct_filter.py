import argparse
import logging
import json
from typing import List, Optional, TypedDict, Literal
from pathlib import Path
from datetime import datetime
import hashlib

from optimade.client import OptimadeClient
from utils import save_structures  # must accept (results, output_folder, max_results, as_cif)

# === CONFIG ===
BASE_OUTPUT_DIR = Path("materials_data")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_PROVIDERS = {
    "alexandria", "cmr", "mp", "mpds", "nmd",
    "odbx", "omdb", "oqmd", "jarvis"
}

Format = Literal["cif", "json"]

class FetchResult(TypedDict):
    output_dir: Path
    files: List[str]
    providers_used: List[str]
    filter: str
    warnings: List[str]

def fetch_structures_with_filter(
    filter_str: str,
    as_format: Format = "cif",
    max_results_per_provider: int = 2,
    providers: Optional[List[str]] = None,
) -> FetchResult:
    """Fetch via RAW OPTIMADE filter (elements-only for first try)."""
    filt = (filter_str or "").strip()
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

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short = hashlib.sha1(filt.encode("utf-8")).hexdigest()[:8]
    out_folder = BASE_OUTPUT_DIR / f"rawfilter_{ts}_{short}"

    files, warns, providers_seen = save_structures(
        results,
        out_folder,
        max_results_per_provider,
        as_cif=(as_format == "cif"),
    )

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

# ---------- CLI TEST HARNESS (elements-only) ----------
def main():
    logging.basicConfig(level="INFO")

    # Demo A: HAS ALL (no LENGTH/npd/formula)
    resA = fetch_structures_with_filter(
        'elements HAS ALL "Al","O","Mg"',
        as_format="cif",
        max_results_per_provider=2
    )
    print("\n[Demo A] HAS ALL -> CIF")
    print(json.dumps(resA, indent=2, default=str))

    # Demo B: HAS ANY
    resB = fetch_structures_with_filter(
        'elements HAS ANY "Al","O"',
        as_format="json",
        max_results_per_provider=1
    )
    print("\n[Demo B] HAS ANY -> JSON")
    print(json.dumps(resB, indent=2, default=str))

    # Demo C: HAS ONLY (exact element set, still no LENGTH)
    resC = fetch_structures_with_filter(
        'elements HAS ONLY "Si","O"',
        as_format="cif",
        max_results_per_provider=1,
        providers=["mp", "jarvis"]  # show provider override
    )
    print("\n[Demo C] HAS ONLY (Si,O) -> CIF from MP & JARVIS")
    print(json.dumps(resC, indent=2, default=str))

if __name__ == "__main__":
    main()