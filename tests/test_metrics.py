"""P4.2 metrics.jsonl 寫入驗收。

- 每次 CLI 執行末尾寫一行 JSON 到 ~/.cache/tfda/metrics.jsonl
- query_type / result_count / duration_ms 必填
- fallback_used 正確記錄（alias / suggest）
- query 欄位預設不記（PII），--log-query 才記
- --no-metrics 完全不寫
- 寫入失敗不 crash 主流程
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from tfda_metrics import record

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


def _run_cli(args, home):
    env = {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
        "LC_ALL": "C.UTF-8",
    }
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "query_tfda.py"), *args],
        capture_output=True, text=True, env=env, timeout=30,
    )


def _read_metrics(home) -> list:
    path = home / ".cache" / "tfda" / "metrics.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ───── record() 純函式 ─────

def test_record_writes_jsonl(tmp_path):
    mfile = tmp_path / "metrics.jsonl"
    record(query_type="company", result_count=8, duration_ms=123.4,
           metrics_file=mfile)
    record(query_type="manufacturer", result_count=4, duration_ms=55.5,
           fallback_used=["alias"], metrics_file=mfile)
    lines = mfile.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    e1 = json.loads(lines[0])
    e2 = json.loads(lines[1])
    assert e1["query_type"] == "company"
    assert e1["result_count"] == 8
    assert "ts" in e1
    assert e2["fallback_used"] == ["alias"]


def test_record_pii_opt_in(tmp_path):
    """query 欄位預設不寫；明確傳 query 參數才寫。"""
    mfile = tmp_path / "metrics.jsonl"
    record(query_type="company", result_count=1, duration_ms=1.0,
           metrics_file=mfile)
    entry = json.loads(mfile.read_text().splitlines()[0])
    assert "query" not in entry

    record(query_type="company", result_count=1, duration_ms=1.0,
           query="醫兆", metrics_file=mfile)
    entry = json.loads(mfile.read_text().splitlines()[1])
    assert entry["query"] == "醫兆"


def test_record_survives_write_error(tmp_path):
    """目標路徑不可寫時不 raise，僅 debug log。"""
    readonly = tmp_path / "readonly_dir"
    readonly.mkdir()
    readonly.chmod(0o444)
    try:
        record(query_type="x", metrics_file=readonly / "m.jsonl")
    finally:
        readonly.chmod(0o755)


# ───── CLI 整合 ─────

def test_cli_writes_metric_entry(tmp_path):
    _seed_cache(tmp_path)
    r = _run_cli(["--company", "醫兆"], tmp_path)
    assert r.returncode == 0
    entries = _read_metrics(tmp_path)
    assert len(entries) == 1
    e = entries[0]
    assert e["query_type"] == "company"
    assert e["result_count"] >= 7
    assert e["duration_ms"] > 0
    assert e["fallback_used"] == []
    assert "query" not in e  # PII 預設不記


def test_cli_alias_fallback_recorded(tmp_path):
    _seed_cache(tmp_path)
    r = _run_cli(["--manufacturer", "愛科萊"], tmp_path)
    assert r.returncode == 0
    entries = _read_metrics(tmp_path)
    assert entries[-1]["fallback_used"] == ["alias"]


def test_cli_suggest_fallback_recorded(tmp_path):
    """0 筆且相近建議可命中時，suggest 進 fallback_used。"""
    _seed_cache(tmp_path)
    r = _run_cli(["--company", "醫趙"], tmp_path)
    assert r.returncode == 0
    entries = _read_metrics(tmp_path)
    assert "suggest" in entries[-1]["fallback_used"]


def test_cli_log_query_flag(tmp_path):
    _seed_cache(tmp_path)
    r = _run_cli(["--company", "醫兆", "--log-query"], tmp_path)
    assert r.returncode == 0
    entries = _read_metrics(tmp_path)
    assert entries[-1]["query"] == "醫兆"


def test_cli_no_metrics_flag(tmp_path):
    _seed_cache(tmp_path)
    r = _run_cli(["--company", "醫兆", "--no-metrics"], tmp_path)
    assert r.returncode == 0
    entries = _read_metrics(tmp_path)
    assert entries == []


def test_cli_cache_age_hours_recorded(tmp_path):
    _seed_cache(tmp_path)
    r = _run_cli(["--company", "醫兆"], tmp_path)
    assert r.returncode == 0
    entry = _read_metrics(tmp_path)[-1]
    assert "cache_age_hours" in entry
    assert entry["cache_age_hours"] >= 0


def test_cli_multiple_runs_appended(tmp_path):
    _seed_cache(tmp_path)
    _run_cli(["--company", "醫兆"], tmp_path)
    _run_cli(["--manufacturer", "ARKRAY"], tmp_path)
    _run_cli(["--qsd", "醫兆"], tmp_path)
    entries = _read_metrics(tmp_path)
    assert len(entries) == 3
    assert {e["query_type"] for e in entries} == {"company", "manufacturer", "qsd"}
