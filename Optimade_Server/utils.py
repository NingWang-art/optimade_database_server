
import os
import time

from pathlib import Path

from pymatgen.core import Composition

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

