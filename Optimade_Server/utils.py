import os
import time
import logging
import json
from pathlib import Path
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


def upload_file_to_oss(file_path: Path) -> str:
    """
    上传文件至 OSS, 返回公开访问链接
    """
    auth = oss2.ProviderAuth(EnvironmentVariableCredentialsProvider())
    endpoint = os.environ["OSS_ENDPOINT"]
    bucket_name = os.environ["OSS_BUCKET_NAME"]
    bucket = oss2.Bucket(auth, endpoint, bucket_name)

    ext = file_path.suffix.lower().lstrip('.')
    oss_filename = f"{ext}_{file_path.name}_{int(time.time())}.{ext}"
    oss_path = f"retrosyn/{oss_filename}"

    with open(file_path, "rb") as f:
        bucket.put_object(oss_path, f)

    region = endpoint.split('.')[0].replace("oss-", "")
    return f"https://{bucket_name}.oss-{region}.aliyuncs.com/{oss_path}"


def save_structures(results, output_folder: Path, max_results: int, as_cif: bool):
    output_folder.mkdir(parents=True, exist_ok=True)
    structures_by_filter = results.get("structures", {})

    for filter_key, provider_dict in structures_by_filter.items():
        for provider_url, content in provider_dict.items():
            parsed = urlparse(provider_url)
            netloc = parsed.netloc.replace('.', '_')
            path = parsed.path.strip('/').replace('/', '_')
            provider_name = f"{netloc}_{path}" if path else netloc

            data_list = content.get("data", [])
            logging.info(f"Found {len(data_list)} structures from provider: {provider_name}")

            for i, structure_data in enumerate(data_list[:max_results]):
                suffix = "cif" if as_cif else "json"
                filename = f"{provider_name}_{i}.{suffix}"
                file_path = output_folder / filename

                try:
                    if as_cif:
                        cif_content = Structure(structure_data).convert('cif')
                        if not cif_content.strip():
                            raise ValueError("CIF content is empty")
                        with open(file_path, "w") as f:
                            f.write(cif_content)
                    else:
                        with open(file_path, "w") as f:
                            json.dump(structure_data, f, indent=2)

                    logging.debug(f"Saved structure to {file_path}")

                except Exception as e:
                    logging.warning(f"Failed to save structure from {provider_name} #{i}: {e}")



