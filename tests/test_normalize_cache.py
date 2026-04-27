"""P5.3 Normalize 快取驗收。

- load_normalized 第一次會寫 {dataset}.norm.json（source_mtime + rows）
- 第二次命中快取（跳過 normalize）→ 速度顯著快於首次
- CSV mtime 變動 → 快取失效並重建
- 損毀的 norm.json → 自動重建（不 crash）
- invalidate_norm_cache 清除
- 禁用 pickle：確認產出檔為合法 JSON（不能含 pickle opcode）
"""

import json
import time
from pathlib import Path

import pytest

# conftest.py 的 isolated_cache fixture 已 autouse，
# 這裡只要在每個 test 用 isolated_cache 取得路徑即可。


@pytest.fixture(autouse=True)
def _enable_norm_cache(monkeypatch):
    """P5.3 預設關閉；測試明確開啟 TFDA_NORM_CACHE=1 驗證快取邏輯。"""
    monkeypatch.setenv("TFDA_NORM_CACHE", "1")


def _seed_csv(cache_dir, dataset):
    """把 fixture 複製到 cache_dir 並寫 meta，模擬已下載 CSV。"""
    import shutil
    from datetime import datetime

    src = Path(__file__).parent / "fixtures" / f"{dataset}_sample.csv"
    dst = cache_dir / f"{dataset}.csv"
    shutil.copy(src, dst)
    meta = cache_dir / f"{dataset}_meta.json"
    meta.write_text(json.dumps({
        "downloaded_at": datetime.now().isoformat(),
        "info_id": 0,
        "dataset_name": dataset,
    }))
    return dst


# ───── 基本快取生命週期 ─────

def test_first_call_builds_norm_cache(isolated_cache):
    _seed_csv(isolated_cache, "license")
    from tfda_datasets import load_normalized
    norm_path = isolated_cache / "license.norm.json"
    assert not norm_path.exists()

    rows = load_normalized("license")
    assert len(rows) >= 10
    assert norm_path.exists()

    data = json.loads(norm_path.read_text(encoding="utf-8"))
    assert "source_mtime" in data
    assert "rows" in data
    assert data["rows"] == rows


def test_second_call_uses_cache(isolated_cache):
    _seed_csv(isolated_cache, "license")
    from tfda_datasets import load_normalized
    first = load_normalized("license")
    norm_path = isolated_cache / "license.norm.json"
    first_mtime = norm_path.stat().st_mtime

    time.sleep(0.01)
    second = load_normalized("license")
    # 結果相等、norm 檔未重寫
    assert first == second
    assert norm_path.stat().st_mtime == first_mtime


def test_csv_mtime_change_invalidates(isolated_cache):
    csv_path = _seed_csv(isolated_cache, "license")
    from tfda_datasets import load_normalized
    load_normalized("license")
    norm_path = isolated_cache / "license.norm.json"
    old_source_mtime = json.loads(norm_path.read_text())["source_mtime"]

    # 改 CSV mtime（模擬重新下載）
    import os
    new_time = old_source_mtime + 100
    os.utime(csv_path, (new_time, new_time))

    load_normalized("license")
    new_source_mtime = json.loads(norm_path.read_text())["source_mtime"]
    assert new_source_mtime == new_time
    assert new_source_mtime != old_source_mtime


def test_corrupted_norm_json_auto_rebuilt(isolated_cache):
    _seed_csv(isolated_cache, "license")
    norm_path = isolated_cache / "license.norm.json"
    norm_path.write_text("{ not valid json")

    from tfda_datasets import load_normalized
    rows = load_normalized("license")
    assert len(rows) >= 10
    # 已被重建
    assert json.loads(norm_path.read_text())["rows"] == rows


def test_invalidate_norm_cache_clears_all(isolated_cache):
    for ds in ("license", "leaflet", "qsd"):
        _seed_csv(isolated_cache, ds)
    from tfda_datasets import invalidate_norm_cache, load_normalized
    for ds in ("license", "leaflet", "qsd"):
        load_normalized(ds)
    # 所有 norm.json 都存在
    for ds in ("license", "leaflet", "qsd"):
        assert (isolated_cache / f"{ds}.norm.json").exists()

    invalidate_norm_cache()
    for ds in ("license", "leaflet", "qsd"):
        assert not (isolated_cache / f"{ds}.norm.json").exists()


def test_invalidate_norm_cache_single(isolated_cache):
    _seed_csv(isolated_cache, "license")
    _seed_csv(isolated_cache, "qsd")
    from tfda_datasets import invalidate_norm_cache, load_normalized
    load_normalized("license")
    load_normalized("qsd")

    invalidate_norm_cache("license")
    assert not (isolated_cache / "license.norm.json").exists()
    assert (isolated_cache / "qsd.norm.json").exists()


# ───── 預設行為：TFDA_NORM_CACHE 未設定時不寫檔 ─────

def test_default_does_not_write_norm_cache(isolated_cache, monkeypatch):
    """未設定 TFDA_NORM_CACHE 時不該產生 norm.json（實測對 stdlib json
    無效能優勢，預設不啟用避免佔磁碟）。"""
    monkeypatch.delenv("TFDA_NORM_CACHE", raising=False)
    _seed_csv(isolated_cache, "license")
    from tfda_datasets import load_normalized
    rows = load_normalized("license")
    assert len(rows) >= 10
    assert not (isolated_cache / "license.norm.json").exists()


def test_norm_cache_zero_also_disabled(isolated_cache, monkeypatch):
    monkeypatch.setenv("TFDA_NORM_CACHE", "0")
    _seed_csv(isolated_cache, "license")
    from tfda_datasets import load_normalized
    load_normalized("license")
    assert not (isolated_cache / "license.norm.json").exists()


# ───── 安全性：禁用 pickle ─────

def test_norm_cache_is_plain_json(isolated_cache):
    """norm 快取必須為合法 JSON，禁用 pickle（避免 RCE 風險）。"""
    _seed_csv(isolated_cache, "license")
    from tfda_datasets import load_normalized
    load_normalized("license")
    norm_path = isolated_cache / "license.norm.json"
    content = norm_path.read_bytes()
    # 應能被 json.loads（若是 pickle，首 byte 通常是 0x80）
    assert content[:1] != b"\x80", "疑似 pickle opcode 開頭"
    json.loads(content.decode("utf-8"))
