"""P4.3 --update-cache 後的 runtime schema drift 偵測。

驗證 scripts/tfda_schema_check 功能：
- check_dataset 對比缺失/新增欄位
- check_all_caches 可跑遍所有 dataset
- report_and_log 正確寫 log 檔
- 無 drift 時不寫 log 檔
"""

from pathlib import Path

from tfda_schema_check import check_all_caches, check_dataset, report_and_log

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _seed_cache(home, datasets=("license", "leaflet", "qsd")):
    cache = home / ".cache" / "tfda"
    cache.mkdir(parents=True, exist_ok=True)
    for key in datasets:
        fname = f"{key}_sample.csv"
        src = FIXTURES_DIR / fname
        if src.exists():
            (cache / f"{key}.csv").write_bytes(src.read_bytes())
    return cache


# ───── check_dataset 純函式 ─────

def test_check_dataset_no_drift_on_fixture(tmp_path, monkeypatch):
    """fixture 應符合 schema。"""
    import tfda_schema_check
    monkeypatch.setattr(tfda_schema_check, "_cache_dir", lambda: _seed_cache(tmp_path))
    diff = check_dataset("license", _seed_cache(tmp_path) / "license.csv")
    assert diff["missing_required"] == []
    assert diff["unexpected"] == []


def test_check_dataset_detects_unexpected_column(tmp_path):
    """CSV 多出一欄 → 列入 unexpected。"""
    (tmp_path / "bad.csv").write_text(
        "許可證字號,中文品名,申請商名稱,製造廠名稱,有效日期,新增神秘欄位\n"
        "L1,A,Co,M,2025/01/01,x\n",
        encoding="utf-8",
    )
    diff = check_dataset("license", tmp_path / "bad.csv")
    assert "新增神秘欄位" in diff["unexpected"]


def test_check_dataset_detects_missing_required(tmp_path):
    """CSV 缺必要欄位 → 列入 missing_required。"""
    (tmp_path / "bad.csv").write_text(
        "許可證字號,中文品名\nL1,A\n", encoding="utf-8",
    )
    diff = check_dataset("license", tmp_path / "bad.csv")
    assert "申請商名稱" in diff["missing_required"]


def test_check_dataset_unknown_dataset(tmp_path):
    (tmp_path / "x.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    diff = check_dataset("nonexistent_schema", tmp_path / "x.csv")
    assert diff == {"missing_required": [], "missing_known": [], "unexpected": []}


# ───── check_all_caches ─────

def test_check_all_caches_returns_three_datasets(tmp_path, monkeypatch):
    import tfda_schema_check
    cache = _seed_cache(tmp_path)
    monkeypatch.setattr(tfda_schema_check, "_cache_dir", lambda: cache)
    results = check_all_caches()
    assert set(results.keys()) == {"license", "leaflet", "qsd"}
    for info in results.values():
        assert "diff" in info and "drift" in info


# ───── report_and_log ─────

def test_report_and_log_writes_file_on_drift(tmp_path, monkeypatch):
    import tfda_schema_check
    log_path = tmp_path / "drift.log"
    monkeypatch.setattr(tfda_schema_check, "get_drift_log_path", lambda: log_path)
    results = {
        "license": {
            "diff": {
                "missing_required": [],
                "missing_known": ["英文品名"],
                "unexpected": ["新欄位"],
            },
            "drift": True,
        },
    }
    had = report_and_log(results)
    assert had is True
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "license" in content
    assert "新欄位" in content


def test_report_and_log_noop_when_no_drift(tmp_path, monkeypatch):
    import tfda_schema_check
    log_path = tmp_path / "drift.log"
    monkeypatch.setattr(tfda_schema_check, "get_drift_log_path", lambda: log_path)
    results = {"license": {"diff": {
        "missing_required": [], "missing_known": [], "unexpected": [],
    }, "drift": False}}
    had = report_and_log(results)
    assert had is False
    assert not log_path.exists()
