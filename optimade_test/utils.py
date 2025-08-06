import asyncio
import logging
import os
import shutil
import tarfile
import time
from pathlib import Path
from typing import Dict, List, Tuple
from dotenv import load_dotenv

import aiofiles
import aiohttp
import oss2
from oss2.credentials import EnvironmentVariableCredentialsProvider

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
load_dotenv()



async def extract_and_upload_files(tgz_url: str, temp_dir: str = "./tmp") -> dict:
    """
    下载 TGZ 文件，提取其中的 .cif 和 .json 文件，并上传到 OSS
    :param tgz_url: 要下载的 TGZ 文件的 URL
    :param temp_dir: 临时目录路径
    :return: 每个文件的上传结果字典
    """
    temp_path = Path(temp_dir)
    temp_path.mkdir(exist_ok=True, parents=True)

    try:
        # 下载并提取文件
        target_files = await extract_target_files_from_tgz_url(tgz_url, temp_path)

        # 上传任务
        upload_tasks = [upload_file_to_oss(file_path) for file_path in target_files]
        results = await asyncio.gather(*upload_tasks)

        return {filename: result for filename, result in results}

    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


async def upload_file_to_oss(file_path: Path) -> Tuple[str, dict]:
    """
    上传二进制文件到 OSS
    :param file_path: 要上传的文件路径
    :return: 文件名 和 上传结果字典
    """
    def _sync_upload(file_data: bytes, oss_path: str) -> dict:
        try:
            auth = oss2.ProviderAuth(EnvironmentVariableCredentialsProvider())
            endpoint = os.environ["OSS_ENDPOINT"]
            bucket_name = os.environ["OSS_BUCKET_NAME"]
            bucket = oss2.Bucket(auth, endpoint, bucket_name)

            bucket.put_object(oss_path, file_data)
            return {
                "status": "success",
                "oss_path": f"https://{bucket_name}.oss-cn-zhangjiakou.aliyuncs.com/{oss_path}",
            }
        except Exception as e:
            logger.exception(f"OSS 上传失败: {oss_path} error={str(e)}")
            return {"status": "failed", "reason": str(e)}

    async with aiofiles.open(file_path, 'rb') as f:
        file_data = await f.read()

    ext = file_path.suffix.lower().lstrip('.')
    oss_filename = f"{ext}_{file_path.name}_{int(time.time())}.{ext}"
    oss_path = f"retrosyn/{oss_filename}"

    result = await asyncio.to_thread(_sync_upload, file_data, oss_path)
    return file_path.name, result


async def extract_target_files_from_tgz_url(tgz_url: str, temp_path: Path) -> List[Path]:
    """
    下载并解压 TGZ 文件，提取其中的 .cif 和 .json 文件
    """
    async with aiohttp.ClientSession() as session:
        tgz_path = temp_path / "downloaded.tgz"
        await download_file(session, tgz_url, tgz_path)
        await extract_tarfile(tgz_path, temp_path)
        return await find_cif_json_files(temp_path)


async def download_file(session: aiohttp.ClientSession, url: str, dest: Path) -> None:
    """
    异步下载文件
    """
    async with session.get(url) as response:
        response.raise_for_status()
        async with aiofiles.open(dest, 'wb') as f:
            async for chunk in response.content.iter_chunked(8192):
                await f.write(chunk)


async def extract_tarfile(tgz_path: Path, extract_to: Path) -> None:
    """
    异步解压 TGZ 文件
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: tarfile.open(tgz_path).extractall(extract_to)
    )


async def find_cif_json_files(directory: Path) -> List[Path]:
    """
    查找所有 .cif 和 .json 文件
    """
    loop = asyncio.get_running_loop()

    def _sync_find():
        return list(directory.rglob("*.cif")) + list(directory.rglob("*.json"))

    return await loop.run_in_executor(None, _sync_find)


if __name__ == "__main__":
    result = asyncio.run(
        extract_and_upload_files(
            tgz_url='https://bohrium.oss-cn-zhangjiakou.aliyuncs.com/907139/912472/store/a510ee75-3511-488c-a3d1-7660d5db2436/outputs/output_dir/FeO_20250806_144325.tgz'
        )
    )
    print(result)