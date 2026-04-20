"""TFDA 資料集下載、讀取、快取管理模組。

支援從 data.fda.gov.tw 下載醫療器材相關資料集，
自動處理 ZIP 壓縮與 CSV 讀取，並提供本地快取機制。
"""

import csv
import io
import json
import logging
import os
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

log = logging.getLogger("tfda")

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
            log.warning("[離線] 使用本地快取（資料日期：%s）", cache_date)
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
    """強制更新所有資料集快取。CSV 變動後同步清除 normalize 快取。"""
    for key, ds in DATASETS.items():
        log.info("  下載 %s（InfoId=%s）...", ds["name"], ds["info_id"])
        try:
            _download_dataset(key, force=True)
            path = _get_cache_path(key)
            size_mb = path.stat().st_size / (1024 * 1024)
            log.info("  完成 (%.1f MB)", size_mb)
        except Exception as e:
            log.error("  失敗：%s", e)
    # 強制刷新 normalize 快取（下次查詢會用新 mtime 重建）
    invalidate_norm_cache()


def _get_norm_cache_path(dataset_key: str) -> Path:
    """normalize 後結果的 JSON 快取路徑。"""
    return CACHE_DIR / f"{dataset_key}.norm.json"


def load_normalized(dataset_key: str) -> List[Dict[str, str]]:
    """載入並回傳已 normalize 的 rows。

    行為由 `TFDA_NORM_CACHE` 環境變數控制：
    - 未設定或 "0"（預設）：直接 load + normalize，不讀寫 norm 快取。
      實測 150k 筆 stdlib json 解析與 CSV+normalize 耗時接近，
      預設不啟用以避免多佔 ~230MB 磁碟。
    - "1"：啟用 JSON 快取；存在且 source_mtime 相符時直接讀取。
      適用場景：單一 CLI 短時間內多次呼叫（pipeline），或未來改用
      orjson / pyarrow 加速 JSON 解析時取得額外效益。

    禁用 pickle：JSON 既可讀又安全，schema 變更不會 silent 腐敗。
    """
    # 為避免循環 import，在函式內 import normalize
    from tfda_normalize import normalize_dataset

    csv_path = _download_dataset(dataset_key)
    use_cache = os.environ.get("TFDA_NORM_CACHE", "0") == "1"
    norm_path = _get_norm_cache_path(dataset_key)
    csv_mtime = csv_path.stat().st_mtime

    if use_cache and norm_path.exists():
        try:
            with open(norm_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("source_mtime") == csv_mtime:
                log.debug("載入 normalize 快取：%s", dataset_key)
                return cached["rows"]
        except (json.JSONDecodeError, KeyError, OSError):
            pass  # 損毀或 schema 改 → 重建

    # 讀 CSV + normalize
    rows = load_dataset(dataset_key)
    normalized = normalize_dataset(rows, dataset_key)

    # 僅在明確啟用時才寫入 norm 快取
    if use_cache:
        try:
            with open(norm_path, "w", encoding="utf-8") as f:
                json.dump({
                    "source_mtime": csv_mtime,
                    "rows": normalized,
                }, f, ensure_ascii=False)
        except OSError as e:
            log.debug("寫 normalize 快取失敗（非致命）：%s", e)
    return normalized


def invalidate_norm_cache(dataset_key: Optional[str] = None) -> None:
    """手動清除 normalize 快取。dataset_key=None 時清全部。"""
    keys = [dataset_key] if dataset_key else list(DATASETS.keys())
    for k in keys:
        p = _get_norm_cache_path(k)
        if p.exists():
            p.unlink()


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
