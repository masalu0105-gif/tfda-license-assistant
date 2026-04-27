"""TFDA 開放資料 schema drift 偵測。

在 --update-cache 後執行，比對下載的 CSV headers 與 schema/*.json
所記錄的基準，把差異寫入 ~/.cache/tfda/schema_drift.log 並印 WARNING。

不 raise 任何例外：schema check 屬觀察性功能，不該擋下主流程。

schema 檔位於 repo 根目錄的 schema/ 資料夾（與 scripts/ 同層）。
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("tfda")

# schema/ 位於 scripts/ 的父目錄
_SCHEMA_DIR = Path(__file__).parent.parent / "schema"


def _cache_dir() -> Path:
    return Path.home() / ".cache" / "tfda"


def get_drift_log_path() -> Path:
    return _cache_dir() / "schema_drift.log"


def _load_schema(dataset: str) -> Optional[dict]:
    path = _SCHEMA_DIR / f"{dataset}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _read_csv_headers(csv_path: Path) -> List[str]:
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader, [])
    return [h.strip() for h in headers]


def check_dataset(dataset: str, csv_path: Path) -> Dict[str, list]:
    """比對單一資料集 CSV 與 schema。回傳 diff dict。

    回傳 keys:
      missing_required：必要欄位缺失
      missing_known：known 欄位消失
      unexpected：出現未在 known 宣告的新欄位
    """
    diff = {"missing_required": [], "missing_known": [], "unexpected": []}
    schema = _load_schema(dataset)
    if schema is None:
        return diff
    if not csv_path.exists():
        return diff

    actual = set(_read_csv_headers(csv_path))
    known = set(schema.get("known_fields", []))
    required = set(schema.get("required_fields", []))

    diff["missing_required"] = sorted(required - actual)
    diff["missing_known"] = sorted((known - required) - actual)
    diff["unexpected"] = sorted(actual - known)
    return diff


def check_all_caches() -> Dict[str, dict]:
    """對 cache/*.csv 逐一跑 check_dataset，回傳整體 diff 結構。"""
    overall = {}
    for dataset in ("license", "leaflet", "qsd"):
        csv_path = _cache_dir() / f"{dataset}.csv"
        diff = check_dataset(dataset, csv_path)
        has_drift = any(diff.values())
        overall[dataset] = {"diff": diff, "drift": has_drift}
    return overall


def report_and_log(results: Dict[str, dict]) -> bool:
    """把 drift 結果印 WARNING 並追加 drift log。回傳是否有 drift。"""
    drift_log = get_drift_log_path()
    drift_log.parent.mkdir(parents=True, exist_ok=True)

    any_drift = False
    log_lines = []
    for dataset, info in results.items():
        if not info["drift"]:
            continue
        any_drift = True
        diff = info["diff"]
        log.warning("Schema drift 偵測：%s", dataset)
        for key, label in (
            ("missing_required", "缺少必要欄位"),
            ("missing_known", "缺少已知欄位"),
            ("unexpected", "出現未知新欄位"),
        ):
            if diff[key]:
                log.warning("  %s：%s", label, diff[key])
                log_lines.append(f"[{dataset}] {label}：{diff[key]}")

    if any_drift:
        ts = datetime.now().isoformat()
        with open(drift_log, "a", encoding="utf-8") as f:
            f.write(f"\n=== {ts} ===\n")
            for line in log_lines:
                f.write(line + "\n")
    return any_drift
