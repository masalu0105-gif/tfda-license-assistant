"""P3.2 中英文廠牌 alias fallback 驗收。

測試：
- aliases.json 結構正確
- expand_manufacturer/company 雙向展開
- search_with_alias_fallback 0 筆重試機制
- 查「愛科萊」應透過 alias 查到 ARKRAY 結果
- 非 alias 查詢的 regression（ARKRAY 直接查到時不走 alias 路徑）
"""

import json
from pathlib import Path

from tfda_aliases import (
    expand_company,
    expand_manufacturer,
    load_aliases,
)
from tfda_search import (
    search_company_with_alias,
    search_manufacturer_with_alias,
)

ALIASES_PATH = Path(__file__).parent.parent / "scripts" / "aliases.json"


# ───── aliases.json 結構 ─────

def test_aliases_json_valid():
    assert ALIASES_PATH.exists()
    data = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
    assert "version" in data
    assert "updated_at" in data
    assert "manufacturers" in data
    assert isinstance(data["manufacturers"], dict)


def test_aliases_has_core_entries():
    data = load_aliases()
    mfg = data["manufacturers"]
    assert "ARKRAY" in mfg
    assert "Sysmex" in mfg
    assert "Roche" in mfg
    assert "Abbott" in mfg


def test_aliases_no_duplicate_per_group():
    data = load_aliases()
    for canonical, aliases in data["manufacturers"].items():
        assert len(aliases) == len(set(aliases)), f"{canonical} 有重複 alias"


# ───── expand_manufacturer ─────

def test_expand_canonical_to_aliases():
    """查 canonical 名應展開整組。"""
    result = expand_manufacturer("ARKRAY")
    assert "愛科萊" in result
    assert "ARKRAY Inc." in result


def test_expand_alias_to_canonical():
    """查 alias 應展開整組（包含 canonical）。"""
    result = expand_manufacturer("愛科萊")
    assert "ARKRAY" in result
    assert "ARKRAY Inc." in result


def test_expand_case_insensitive():
    result = expand_manufacturer("arkray")
    assert "ARKRAY" in result


def test_expand_unknown_returns_only_self():
    result = expand_manufacturer("未知廠牌 XYZ")
    assert result == ["未知廠牌 XYZ"]


def test_expand_company():
    result = expand_company("醫兆")
    assert "醫兆科技股份有限公司" in result


# ───── search_manufacturer_with_alias 整合 ─────

def test_alias_fallback_triggers_on_zero_results(normalized_license_rows):
    """查「愛科萊」直接命中 0 筆（fixture 只有 ARKRAY），應透過 alias 查到結果。"""
    results, alias_used = search_manufacturer_with_alias(
        normalized_license_rows, "愛科萊"
    )
    assert len(results) >= 4, "愛科萊 透過 alias 展開至 ARKRAY 後應命中"
    assert alias_used is not None
    assert "ARKRAY" in alias_used


def test_alias_not_used_when_primary_hits(normalized_license_rows):
    """直接查 ARKRAY 能命中，不應走 alias 路徑。"""
    results, alias_used = search_manufacturer_with_alias(
        normalized_license_rows, "ARKRAY"
    )
    assert len(results) >= 4
    assert alias_used is None  # primary 命中不走 alias


def test_alias_returns_empty_when_no_match_at_all(normalized_license_rows):
    """完全查不到的名稱：無 alias 可試 → 空結果 + None。"""
    results, alias_used = search_manufacturer_with_alias(
        normalized_license_rows, "完全不存在的廠牌 XYZ 123"
    )
    assert results == []
    assert alias_used is None


def test_sysmex_chinese_alias(normalized_license_rows):
    """查「希森美康」→ alias → Sysmex。"""
    results, alias_used = search_manufacturer_with_alias(
        normalized_license_rows, "希森美康"
    )
    assert len(results) >= 2
    assert alias_used is not None


def test_company_alias_fallback(normalized_license_rows):
    """公司 alias：醫兆 → 醫兆科技股份有限公司（fixture 全名存值）。

    fixture 存「醫兆科技股份有限公司」；查「醫兆」能直接 contains 命中，
    不需走 alias，此 case 驗證 primary 優先 + alias wrapper 包裝正確。
    """
    results, alias_used = search_company_with_alias(
        normalized_license_rows, "醫兆"
    )
    assert len(results) >= 7
    # primary 即命中 contains，不應經 alias
    assert alias_used is None
