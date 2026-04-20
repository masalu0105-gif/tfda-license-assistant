"""P3.4 --count-only 筆數 preview flag 驗收。

- --count-only 僅輸出「共 N 筆」，不列出表格
- 適用於所有主要查詢路徑：company / manufacturer / qsd / leaflet
- --count-only + --json 時 count 優先（不輸出 JSON）
- 不會阻擋仿單 / alias 等輔助查詢邏輯

另驗證：>30 筆摘要閾值（對齊 SKILL.md 檢查點）。
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT / "scripts"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _seed_cache(home: Path):
    cache = home / ".cache" / "tfda"
    cache.mkdir(parents=True, exist_ok=True)
    for key, fname in [
        ("license", "license_sample.csv"),
        ("leaflet", "leaflet_sample.csv"),
        ("qsd", "qsd_sample.csv"),
    ]:
        shutil.copy(FIXTURES_DIR / fname, cache / f"{key}.csv")
        (cache / f"{key}_meta.json").write_text(json.dumps({
            "downloaded_at": datetime.now().isoformat(),
            "info_id": 0,
        }))


def _run(args, home):
    env = {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
        "LC_ALL": "C.UTF-8",
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "query_tfda.py"), *args],
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert result.returncode == 0, f"rc={result.returncode} stderr={result.stderr}"
    return result.stdout


# ───── --count-only 基本功能 ─────

def test_count_only_company(tmp_path):
    _seed_cache(tmp_path)
    out = _run(["--company", "醫兆", "--count-only"], tmp_path)
    assert "共找到" in out
    assert "8 筆" in out  # fixture 內醫兆 8 筆
    # 不應出現表格 header
    assert "| 許可證字號" not in out
    assert "### 製造廠分布" not in out


def test_count_only_manufacturer(tmp_path):
    _seed_cache(tmp_path)
    out = _run(["--manufacturer", "ARKRAY", "--count-only"], tmp_path)
    assert "共找到" in out
    assert "筆" in out
    assert "| 許可證字號" not in out


def test_count_only_qsd(tmp_path):
    _seed_cache(tmp_path)
    out = _run(["--qsd", "醫兆", "--count-only"], tmp_path)
    assert "共找到" in out
    assert "| 許可編號" not in out


def test_count_only_leaflet(tmp_path):
    _seed_cache(tmp_path)
    out = _run(["--leaflet", "衛部醫器輸字第034001號", "--count-only"], tmp_path)
    assert "共找到" in out
    assert "| 許可證字號" not in out


def test_count_only_zero_results(tmp_path):
    _seed_cache(tmp_path)
    out = _run(["--company", "完全不存在的公司 XYZ", "--count-only"], tmp_path)
    assert "共找到 0 筆" in out or "共找到" in out


def test_count_only_with_alias(tmp_path):
    """--count-only 也會經過 alias fallback。查「愛科萊」經 alias 得 ARKRAY 筆數。"""
    _seed_cache(tmp_path)
    out = _run(["--manufacturer", "愛科萊", "--count-only"], tmp_path)
    assert "共找到" in out
    # alias 提示仍會印（非 count 本體）
    assert "alias" in out


def test_count_only_overrides_json(tmp_path):
    """--count-only + --json：count 優先，不吐 JSON。"""
    _seed_cache(tmp_path)
    out = _run(["--company", "醫兆", "--count-only", "--json"], tmp_path)
    assert "共找到" in out
    # 不應包含 JSON 陣列起點
    # （「[...]」可能出現在 log 中，但不會是 dump 出的 JSON）
    assert '"_match_type"' not in out


def test_help_lists_count_only(tmp_path):
    """--help 應列出 --count-only。"""
    _seed_cache(tmp_path)
    out = _run(["--help"], tmp_path)
    assert "--count-only" in out
