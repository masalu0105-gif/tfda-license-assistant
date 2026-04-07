"""TFDA 資料集下載、讀取、快取管理模組。

支援從 data.fda.gov.tw 下載醫療器材相關資料集，
自動處理 ZIP 壓縮與 CSV 讀取，並提供本地快取機制。
"""

import csv
import io
import json
import os
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


# 資料集定義
DATASETS: Dict[str, dict] = {
    "license": {
        "info_id": 68,
        "name": "醫療器材許可證",
        "is_zip": True,
        "csv_filename": "68_2.csv",
    },
    "leaflet": {
        "info_id": 70,
        "name": "仿單/外盒圖檔",
        "is_zip": True,
        "csv_filename": "70_2.csv",
    },
    "qms": {
        "info_id": 111,
        "name": "QMS 製造許可",
        "is_zip": False,
    },
    "qsd": {
        "info_id": 112,
        "name": "QSD 認可登錄",
        "is_zip": False,
    },
}

BASE_URL = "https://data.fda.gov.tw/data/opendata/export/{info_id}/csv"

# 快取目錄（專案根目錄下）
CACHE_DIR = Path.home() / ".cache" / "tfda"
CACHE_TTL_HOURS = int(os.environ.get("TFDA_CACHE_TTL_HOURS", "24"))


def _get_cache_path(dataset_key: str) -> Path:
    """取得資料集快取檔路徑。"""
    return CACHE_DIR / f"{dataset_key}.csv"


def _get_meta_path(dataset_key: str) -> Path:
    """取得快取 metadata 路徑。"""
    return CACHE_DIR / f"{dataset_key}_meta.json"


def _is_cache_valid(dataset_key: str) -> bool:
    """檢查快取是否存在且未過期。"""
    cache_path = _get_cache_path(dataset_key)
    meta_path = _get_meta_path(dataset_key)

    if not cache_path.exists() or not meta_path.exists():
        return False

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        downloaded_at = datetime.fromisoformat(meta["downloaded_at"])
        return datetime.now() - downloaded_at < timedelta(hours=CACHE_TTL_HOURS)
    except (json.JSONDecodeError, KeyError, ValueError):
        return False


def _get_cache_date(dataset_key: str) -> Optional[str]:
    """取得快取下載日期。"""
    meta_path = _get_meta_path(dataset_key)
    if not meta_path.exists():
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return meta.get("downloaded_at", "N/A")[:10]
    except (json.JSONDecodeError, KeyError):
        return None


def _download_dataset(dataset_key: str, force: bool = False) -> Path:
    """下載資料集並存入快取。"""
    if not force and _is_cache_valid(dataset_key):
        return _get_cache_path(dataset_key)

    ds = DATASETS[dataset_key]
    url = BASE_URL.format(info_id=ds["info_id"])
    cache_path = _get_cache_path(dataset_key)
    meta_path = _get_meta_path(dataset_key)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        req = Request(url, headers={"User-Agent": "TFDA-License-Assistant/1.0"})
        with urlopen(req, timeout=60) as resp:
            raw_data = resp.read()
    except (URLError, HTTPError) as e:
        # 離線模式：使用過期快取
        if cache_path.exists():
            cache_date = _get_cache_date(dataset_key)
            print(f"  [離線] 使用本地快取（資料日期：{cache_date}）")
            return cache_path
        raise ConnectionError(
            f"無法下載 {ds['name']}（{url}）。\n"
            f"錯誤：{e}\n"
            f"請確認網路連線，或在有網路環境下執行：\n"
            f"  python scripts/query_tfda.py --update-cache"
        ) from e

    # 處理 ZIP 或直接 CSV
    if ds.get("is_zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw_data)) as zf:
                # 嘗試用預設檔名，找不到就用第一個 .csv
                csv_name = ds.get("csv_filename")
                names = zf.namelist()
                if csv_name and csv_name in names:
                    csv_bytes = zf.read(csv_name)
                else:
                    csv_files = [n for n in names if n.endswith(".csv")]
                    if not csv_files:
                        raise ValueError(f"ZIP 內找不到 CSV 檔案：{names}")
                    csv_bytes = zf.read(csv_files[0])
        except zipfile.BadZipFile:
            # 可能不是 ZIP（API 回傳格式不一致）
            csv_bytes = raw_data
    else:
        csv_bytes = raw_data

    # 嘗試解碼
    csv_text = _decode_csv(csv_bytes)

    with open(cache_path, "w", encoding="utf-8", newline="") as f:
        f.write(csv_text)

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "downloaded_at": datetime.now().isoformat(),
            "source_url": url,
            "info_id": ds["info_id"],
            "dataset_name": ds["name"],
        }, f, ensure_ascii=False, indent=2)

    return cache_path


def _decode_csv(raw_bytes: bytes) -> str:
    """嘗試多種編碼解碼 CSV。"""
    for encoding in ["utf-8-sig", "utf-8", "big5", "cp950", "latin1"]:
        try:
            return raw_bytes.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    raise UnicodeDecodeError("", raw_bytes, 0, len(raw_bytes), "無法以任何已知編碼解碼")


def load_dataset(dataset_key: str, force_download: bool = False) -> List[Dict[str, str]]:
    """載入資料集，回傳 list of dict。"""
    if dataset_key not in DATASETS:
        raise ValueError(f"未知的資料集：{dataset_key}。可用：{list(DATASETS.keys())}")

    cache_path = _download_dataset(dataset_key, force=force_download)

    with open(cache_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            # 清理欄位值的前後空白
            cleaned = {k.strip(): v.strip() if v else "" for k, v in row.items() if k}
            rows.append(cleaned)

    return rows


def update_all_cache() -> None:
    """強制更新所有資料集快取。"""
    for key, ds in DATASETS.items():
        print(f"  下載 {ds['name']}（InfoId={ds['info_id']}）...")
        try:
            _download_dataset(key, force=True)
            path = _get_cache_path(key)
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"  完成 ({size_mb:.1f} MB)")
        except Exception as e:
            print(f"  失敗：{e}")


def get_cache_info() -> Dict[str, dict]:
    """回傳所有資料集的快取狀態。"""
    info = {}
    for key, ds in DATASETS.items():
        cache_path = _get_cache_path(key)
        info[key] = {
            "name": ds["name"],
            "cached": cache_path.exists(),
            "cache_date": _get_cache_date(key),
            "valid": _is_cache_valid(key),
        }
    return info
