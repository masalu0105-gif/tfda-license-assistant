"""測試共用 fixture。

所有 fixture 都使用 tests/fixtures/ 下的去敏樣本資料，
並透過 monkeypatch 隔離真實快取目錄，確保測試不讀寫使用者的 ~/.cache/tfda。
"""

import csv
import os
import sys
from pathlib import Path
from typing import Dict, List

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_csv(path: Path) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [
            {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}
            for row in reader
        ]


@pytest.fixture(scope="session")
def license_rows() -> List[Dict[str, str]]:
    return _load_csv(FIXTURES_DIR / "license_sample.csv")


@pytest.fixture(scope="session")
def leaflet_rows() -> List[Dict[str, str]]:
    return _load_csv(FIXTURES_DIR / "leaflet_sample.csv")


@pytest.fixture(scope="session")
def qsd_rows() -> List[Dict[str, str]]:
    return _load_csv(FIXTURES_DIR / "qsd_sample.csv")


@pytest.fixture(scope="session")
def normalized_license_rows(license_rows):
    from tfda_normalize import normalize_dataset
    return normalize_dataset(license_rows, "license")


@pytest.fixture(scope="session")
def normalized_qsd_rows(qsd_rows):
    from tfda_normalize import normalize_dataset
    return normalize_dataset(qsd_rows, "qsd")


@pytest.fixture(scope="session")
def normalized_leaflet_rows(leaflet_rows):
    from tfda_normalize import normalize_dataset
    return normalize_dataset(leaflet_rows, "leaflet")


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """隔離測試快取目錄，禁止碰到真實 ~/.cache/tfda。"""
    fake_cache = tmp_path / "tfda_cache"
    fake_cache.mkdir()
    import tfda_datasets
    monkeypatch.setattr(tfda_datasets, "CACHE_DIR", fake_cache)
    yield fake_cache


@pytest.fixture
def fixture_cache(isolated_cache, monkeypatch):
    """把 fixture CSV 複製到隔離快取，模擬已下載狀態。"""
    import json
    import shutil
    from datetime import datetime

    mapping = {
        "license": "license_sample.csv",
        "leaflet": "leaflet_sample.csv",
        "qsd": "qsd_sample.csv",
    }
    for key, filename in mapping.items():
        src = FIXTURES_DIR / filename
        if not src.exists():
            continue
        shutil.copy(src, isolated_cache / f"{key}.csv")
        meta = {
            "downloaded_at": datetime.now().isoformat(),
            "source_url": f"fixture://{filename}",
            "info_id": 0,
            "dataset_name": key,
        }
        with open(isolated_cache / f"{key}_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
    return isolated_cache
