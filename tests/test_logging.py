"""P4.1 logging / --quiet / --verbose 驗收。

重點：
- 結果輸出（table / JSON / count）必須走 stdout，不受 logging level 影響
- 進度訊息走 stderr（logger.info）
- --quiet 抑制進度，保留結果與錯誤
- --verbose 開 DEBUG 級
- pipe 場景：--json --quiet 的 stdout 可被 json.loads 直接 parse
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


def _seed_cache(home):
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
    return result


# ───── stdout / stderr 分離 ─────

def test_progress_msgs_on_stderr(tmp_path):
    """「正在載入...」「查詢...」等進度訊息應在 stderr 而非 stdout。"""
    _seed_cache(tmp_path)
    r = _run(["--company", "醫兆"], tmp_path)
    assert r.returncode == 0
    assert "正在載入" in r.stderr
    assert "查詢" in r.stderr
    assert "正在載入" not in r.stdout


def test_table_result_on_stdout(tmp_path):
    """結果表格必須在 stdout。"""
    _seed_cache(tmp_path)
    r = _run(["--company", "醫兆"], tmp_path)
    assert "| 許可證字號" in r.stdout


def test_json_output_on_stdout_only(tmp_path):
    """--json 輸出必須乾淨地在 stdout。"""
    _seed_cache(tmp_path)
    r = _run(["--company", "醫兆", "--json"], tmp_path)
    idx = r.stdout.find("[")
    assert idx >= 0
    data = json.loads(r.stdout[idx:])
    assert isinstance(data, list) and len(data) >= 1


# ───── --quiet ─────

def test_quiet_suppresses_progress(tmp_path):
    """--quiet 時 stderr 應幾乎沒有進度訊息。"""
    _seed_cache(tmp_path)
    r = _run(["--company", "醫兆", "--quiet"], tmp_path)
    assert r.returncode == 0
    assert "正在載入" not in r.stderr
    assert "查詢" not in r.stderr


def test_quiet_preserves_stdout_result(tmp_path):
    _seed_cache(tmp_path)
    r = _run(["--company", "醫兆", "--quiet"], tmp_path)
    assert "| 許可證字號" in r.stdout


def test_quiet_json_pipe_use_case(tmp_path):
    """DoD：--json --quiet 的 stdout 純 JSON，可被 jq parse。"""
    _seed_cache(tmp_path)
    r = _run(["--company", "醫兆", "--json", "--quiet"], tmp_path)
    assert r.returncode == 0
    # stderr 應為空或僅剩 error；stdout 前應無進度訊息
    idx = r.stdout.find("[")
    assert idx >= 0
    before = r.stdout[:idx].strip()
    assert before == "", f"JSON 前有雜訊：{before!r}"
    data = json.loads(r.stdout[idx:])
    assert len(data) >= 1


# ───── --verbose ─────

def test_verbose_still_works(tmp_path):
    """--verbose 至少要不 crash。"""
    _seed_cache(tmp_path)
    r = _run(["--company", "醫兆", "--verbose"], tmp_path)
    assert r.returncode == 0
    assert "| 許可證字號" in r.stdout


def test_quiet_and_verbose_mutual(tmp_path):
    """--quiet 有較高優先權：兩個都給時 quiet 勝。"""
    _seed_cache(tmp_path)
    r = _run(["--company", "醫兆", "--quiet", "--verbose"], tmp_path)
    assert r.returncode == 0
    assert "正在載入" not in r.stderr


# ───── 錯誤仍會印（logger.error） ─────

def test_errors_printed_even_with_quiet(tmp_path):
    """--quiet 不應抑制 error 訊息。"""
    _seed_cache(tmp_path)
    # 模擬錯誤：故意把 license cache 檔刪掉，看 --company 查詢錯誤訊息
    (tmp_path / ".cache" / "tfda" / "license.csv").unlink()
    (tmp_path / ".cache" / "tfda" / "license_meta.json").unlink()
    r = _run(["--company", "醫兆", "--quiet"], tmp_path)
    # 應有 error 訊息（stderr）
    assert "錯誤" in r.stderr or "無法" in r.stderr or r.returncode != 0
