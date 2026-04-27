"""P1.5 將 test-prompts.json 升格為可執行的 smoke test。

每筆 prompt 定義：
- scenario / prompt：人類可讀的場景與自然語言輸入
- expected_cli_args：skill 應該執行的 CLI 參數
- expected_contains：輸出必須包含的關鍵字 list
- expected_row_count_min：最少命中筆數（JSON 或 markdown 表格行）
- expected_json：若為 true，stdout 必須包含可被 json.loads 解析的陣列

測試會：
1. 預先把 fixture CSV 塞到 HOME 下的假快取
2. 用 expected_cli_args 呼叫 query_tfda.py
3. 檢查 expected_contains 全部出現
4. 檢查筆數 ≥ expected_row_count_min
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT / "scripts"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
PROMPTS_PATH = ROOT / "test-prompts.json"


def _load_prompts():
    return json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))


def _seed_cache(home_dir: Path):
    cache = home_dir / ".cache" / "tfda"
    cache.mkdir(parents=True, exist_ok=True)
    for key, fname in [
        ("license", "license_sample.csv"),
        ("leaflet", "leaflet_sample.csv"),
        ("qsd", "qsd_sample.csv"),
    ]:
        src = FIXTURES_DIR / fname
        if src.exists():
            shutil.copy(src, cache / f"{key}.csv")
            (cache / f"{key}_meta.json").write_text(json.dumps({
                "downloaded_at": datetime.now().isoformat(),
                "info_id": 0,
            }))


def _run(args, home_dir: Path):
    """回傳 (stdout, stderr)；contains 檢查用合併，row count 用 stdout。"""
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
        f"CLI 失敗 rc={result.returncode}\nstderr: {result.stderr}"
    )
    return result.stdout, result.stderr


def _count_rows(output: str, *, is_json: bool) -> int:
    """估算輸出中的資料筆數。"""
    if is_json:
        idx = output.find("[")
        if idx < 0:
            return 0
        try:
            return len(json.loads(output[idx:]))
        except json.JSONDecodeError:
            return 0
    # markdown 表格：計算 | 開頭資料列（跳過 header 與 separator）
    count = 0
    in_table = False
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("|---"):
            in_table = True
            continue
        if not line.startswith("|"):
            in_table = False
            continue
        if in_table:
            count += 1
    return count


PROMPTS = _load_prompts()


def test_prompts_file_has_min_10():
    assert len(PROMPTS) >= 10, f"test-prompts.json 只有 {len(PROMPTS)} 筆，DoD 要求 ≥ 10"


def test_prompts_all_have_required_fields():
    for p in PROMPTS:
        for key in ("id", "scenario", "prompt", "expected_cli_args",
                    "expected_row_count_min"):
            assert key in p, f"id={p.get('id')} 缺欄位 {key}"


@pytest.mark.parametrize("prompt", PROMPTS, ids=[f"#{p['id']}_{p['scenario'][:20]}" for p in PROMPTS])
def test_prompt_e2e(prompt, tmp_path):
    _seed_cache(tmp_path)

    stdout, stderr = _run(prompt["expected_cli_args"], tmp_path)
    combined = stdout + stderr

    # 1. 檢查必備字串（合併 stdout+stderr，反映使用者看到的完整畫面）
    for needle in prompt.get("expected_contains", []):
        assert needle in combined, (
            f"prompt #{prompt['id']}：缺少關鍵字 {needle!r}\n"
            f"--- stdout ---\n{stdout[:500]}\n"
            f"--- stderr ---\n{stderr[:500]}"
        )

    # 2. 檢查筆數（僅看 stdout — 結果資料流）
    is_json = prompt.get("expected_json", False)
    rows = _count_rows(stdout, is_json=is_json)
    assert rows >= prompt["expected_row_count_min"], (
        f"prompt #{prompt['id']}：筆數 {rows} < 預期 {prompt['expected_row_count_min']}"
    )

    # 3. JSON 場景額外驗證可 parse
    if is_json:
        idx = stdout.find("[")
        assert idx >= 0
        data = json.loads(stdout[idx:])
        assert isinstance(data, list)
