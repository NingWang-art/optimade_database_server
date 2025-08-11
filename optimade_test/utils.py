import os
import time
import logging
import json
from pathlib import Path
from typing import List, Dict
from optimade.adapters.structures import Structure
from pymatgen.core import Composition

from urllib.parse import urlparse
import oss2
from dotenv import load_dotenv
from oss2.credentials import EnvironmentVariableCredentialsProvider

# === LOAD ENV ===
load_dotenv()

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

    # manifest for convenience
    manifest = {
        "count_files": len(files),
        "providers_seen": providers_seen,
        "files": files,
        "warnings": warnings,
    }
    (output_folder / "summary.json").write_text(json.dumps(manifest, indent=2))
    return files, warnings, providers_seen
