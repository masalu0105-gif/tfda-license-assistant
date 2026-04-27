"""P1.3 CLI end-to-end 測試（golden output 比對）。

- 透過 subprocess 跑 `scripts/query_tfda.py`
- HOME 環境變數導向 tmp_path，預先塞入 fixture CSV 模擬快取
- 輸出經 _normalize_output 濾掉變動部分（cache 日期、匹配類型標籤）
- 與 tests/golden/*.md 比對；首次執行時以 REGEN_GOLDEN=1 產生

場景覆蓋（8 種主要 CLI 用法，對齊 examples/sample_queries.md）：
1. 純 company 查詢
2. 純 manufacturer 查詢
3. 純 reagent 查詢
4. company × manufacturer 組合
5. 單一 license 查詢（含仿單）
6. --qsd 查詢
7. --leaflet 查詢
8. --cache-info
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT / "scripts"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOLDEN_DIR = Path(__file__).parent / "golden"


def _seed_cache(home_dir: Path) -> Path:
    """把 fixture CSV 複製到 home_dir/.cache/tfda 並寫 meta，偽裝為已下載。"""
    cache = home_dir / ".cache" / "tfda"
    cache.mkdir(parents=True, exist_ok=True)
    mapping = {
        "license": "license_sample.csv",
        "leaflet": "leaflet_sample.csv",
        "qsd": "qsd_sample.csv",
    }
    for key, fname in mapping.items():
        src = FIXTURES_DIR / fname
        if not src.exists():
            continue
        shutil.copy(src, cache / f"{key}.csv")
        meta = {
            "downloaded_at": datetime.now().isoformat(),
            "source_url": f"fixture://{fname}",
            "info_id": 0,
            "dataset_name": key,
        }
        (cache / f"{key}_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False)
        )
    return cache


def _run_cli(args, home_dir: Path) -> str:
    """跑 CLI 並回傳 stdout。非零退出碼會讓測試 fail。"""
    env = {
        "HOME": str(home_dir),
        "PATH": os.environ.get("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
        "LC_ALL": "C.UTF-8",
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "query_tfda.py"), *args],
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert result.returncode == 0, (
        f"CLI 失敗 rc={result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    return result.stdout


_CACHE_DATE_RE = re.compile(r"（\d{4}-\d{2}-\d{2}）")
_MATCH_TYPE_RE = re.compile(r"\| (完全匹配|部分匹配|模糊匹配) \|")


def _normalize_output(text: str) -> str:
    """濾掉執行期會變動的部分：快取日期、匹配類型欄位。"""
    text = _CACHE_DATE_RE.sub("（{CACHE_DATE}）", text)
    text = _MATCH_TYPE_RE.sub("| {MATCH} |", text)
    return text.strip() + "\n"


# 場景定義：(id, CLI args, golden 檔名)
SCENARIOS = [
    ("company",       ["--company", "醫兆"],                           "company_medizheng.md"),
    ("manufacturer",  ["--manufacturer", "ARKRAY"],                    "manufacturer_arkray.md"),
    ("reagent",       ["--reagent", "HbA1c"],                          "reagent_hba1c.md"),
    ("combo_co_mfg",  ["--company", "醫兆", "--manufacturer", "ARKRAY"], "combo_medizheng_arkray.md"),
    ("license",       ["--license", "衛部醫器輸字第034001號"],          "license_specific.md"),
    ("qsd",           ["--qsd", "醫兆"],                                "qsd_medizheng.md"),
    ("leaflet",       ["--leaflet", "衛部醫器輸字第034001號"],          "leaflet_specific.md"),
    ("cache_info",    ["--cache-info"],                                 "cache_info.md"),
]


@pytest.mark.parametrize("case_id,args,golden_name", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_cli_golden(case_id, args, golden_name, tmp_path):
    _seed_cache(tmp_path)
    actual = _normalize_output(_run_cli(args, tmp_path))
    golden_path = GOLDEN_DIR / golden_name

    if os.environ.get("REGEN_GOLDEN") == "1":
        GOLDEN_DIR.mkdir(exist_ok=True)
        golden_path.write_text(actual, encoding="utf-8")
        pytest.skip(f"已重建 golden：{golden_name}")

    assert golden_path.exists(), (
        f"缺少 golden 檔：{golden_path}\n"
        f"請先跑：REGEN_GOLDEN=1 pytest tests/test_cli_e2e.py"
    )
    expected = golden_path.read_text(encoding="utf-8")
    assert actual == expected, (
        f"輸出與 golden 不符（{golden_name}）。\n"
        f"--- 預期 ---\n{expected}\n"
        f"--- 實際 ---\n{actual}"
    )


def test_cli_help_does_not_crash(tmp_path):
    """無任何查詢條件 → 顯示 help 不應非零退出。"""
    _seed_cache(tmp_path)
    out = _run_cli([], tmp_path)
    assert "TFDA 醫療器材資料查詢工具" in out or "usage:" in out.lower()


def test_cli_json_output_parseable(tmp_path):
    """--json 輸出必須可被 json.loads 解析（給下游 pipe 用）。"""
    _seed_cache(tmp_path)
    out = _run_cli(["--company", "醫兆", "--json"], tmp_path)
    # stdout 含進度訊息，取第一個 '[' 之後當 JSON
    idx = out.find("[")
    assert idx >= 0, f"找不到 JSON 陣列起點：{out}"
    data = json.loads(out[idx:])
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "_match_type" in data[0]
