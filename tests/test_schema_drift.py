"""P1.4 資料 schema drift 偵測。

目的：當 TFDA 開放資料改變欄位時，CI 可第一時間抓到，
避免 normalize / search / formatter 靜默 return N/A。

Target 選擇：
- 預設（`TFDA_SCHEMA_TARGET=fixture` 或未設）：驗 tests/fixtures/ 下
  的去敏樣本，確保 fixture 自己符合 schema 承諾（CI 永遠跑這個）。
- `TFDA_SCHEMA_TARGET=cache`：驗 ~/.cache/tfda/*.csv，只有本地
  更新快取後才會有資料，不然 skip。此模式用於 `--update-cache`
  後人工或排程跑，驗證 TFDA 源端沒有 drift。

每個 dataset 檢查三項：
1. required_fields 全部存在 → fail
2. 出現未知新欄位 → fail 並列出 diff（嚴格模式，避免靜默腐敗）
3. row count ≥ min_rows → fail
"""

import csv
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SCHEMA_DIR = ROOT / "schema"
FIXTURES_DIR = Path(__file__).parent / "fixtures"

_TARGET = os.environ.get("TFDA_SCHEMA_TARGET", "fixture")

SCHEMA_FILES = list(SCHEMA_DIR.glob("*.json"))


def _load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv_headers_and_count(csv_path: Path) -> tuple:
    """回傳 (headers_list, row_count)。"""
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = sum(1 for _ in reader)
    return [h.strip() for h in headers], rows


def _resolve_target_csv(dataset: str) -> Path | None:
    if _TARGET == "cache":
        path = Path.home() / ".cache" / "tfda" / f"{dataset}.csv"
        return path if path.exists() else None
    # fixture target
    fname_map = {
        "license": "license_sample.csv",
        "leaflet": "leaflet_sample.csv",
        "qsd": "qsd_sample.csv",
    }
    fname = fname_map.get(dataset)
    if not fname:
        return None
    path = FIXTURES_DIR / fname
    return path if path.exists() else None


@pytest.mark.parametrize("schema_path", SCHEMA_FILES,
                         ids=[p.stem for p in SCHEMA_FILES])
def test_required_fields_present(schema_path):
    schema = _load_schema(schema_path)
    csv_path = _resolve_target_csv(schema["dataset"])
    if csv_path is None:
        pytest.skip(f"{_TARGET} 模式下找不到 {schema['dataset']} 的資料")

    headers, _ = _read_csv_headers_and_count(csv_path)
    missing = [f for f in schema["required_fields"] if f not in headers]
    assert not missing, (
        f"[{schema['dataset']}] 必要欄位缺失：{missing}\n"
        f"實際 headers：{headers}\n"
        f"（TFDA 可能已調整欄位名，需同步更新 FIELD_ALIASES 與本 schema）"
    )


@pytest.mark.parametrize("schema_path", SCHEMA_FILES,
                         ids=[p.stem for p in SCHEMA_FILES])
def test_no_unexpected_new_fields(schema_path):
    """嚴格模式：出現未在 known_fields 中的新欄位 → fail。

    這可提醒我們：TFDA 新增欄位時要決定是否納入 normalize，
    而不是靜默忽略。
    """
    schema = _load_schema(schema_path)
    csv_path = _resolve_target_csv(schema["dataset"])
    if csv_path is None:
        pytest.skip(f"{_TARGET} 模式下找不到 {schema['dataset']} 的資料")

    headers, _ = _read_csv_headers_and_count(csv_path)
    unexpected = [h for h in headers if h and h not in schema["known_fields"]]
    assert not unexpected, (
        f"[{schema['dataset']}] 偵測到未知新欄位：{unexpected}\n"
        f"請評估是否納入 FIELD_ALIASES，並更新 schema/{schema['dataset']}.json"
    )


@pytest.mark.parametrize("schema_path", SCHEMA_FILES,
                         ids=[p.stem for p in SCHEMA_FILES])
def test_row_count_sanity(schema_path):
    schema = _load_schema(schema_path)
    csv_path = _resolve_target_csv(schema["dataset"])
    if csv_path is None:
        pytest.skip(f"{_TARGET} 模式下找不到 {schema['dataset']} 的資料")

    _, rows = _read_csv_headers_and_count(csv_path)
    # schema 用 min_rows_real 對應 cache target；fixture 另外命名
    if _TARGET == "cache":
        threshold = schema.get("min_rows_real", 0)
    else:
        threshold = schema.get("min_rows_fixture", 0)
    assert rows >= threshold, (
        f"[{schema['dataset']}] 筆數 {rows} < 預期 {threshold}。"
        f"TFDA 資料可能異常（空檔 / 下載中斷 / 源端下架）"
    )


def test_schema_files_loadable():
    """元測試：schema 目錄至少有 license/leaflet/qsd 三份，都能 parse。"""
    names = {p.stem for p in SCHEMA_FILES}
    assert {"license", "leaflet", "qsd"}.issubset(names)
    for p in SCHEMA_FILES:
        schema = _load_schema(p)
        assert "required_fields" in schema
        assert "known_fields" in schema
        # required 必須是 known 的子集
        missing = set(schema["required_fields"]) - set(schema["known_fields"])
        assert not missing, f"{p.name}: required 含 known 未宣告的欄位 {missing}"
