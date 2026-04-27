"""P0.1 驗收測試：query_tfda.py 組合查詢 dispatch 邏輯。

驗證：
- 32 種（含 license）flag 組合的 primary field 與 cross filters 是否正確
- 2-flag 與 3-flag 組合都有覆蓋
- dead code（args._primary）確實移除
- --company 醫兆 單條件查詢結果筆數不變（回歸）
"""

import itertools

import pytest
from tfda_search import COMBINABLE_FIELDS, apply_cross_filter, plan_query, search_by_company


class _Args:
    """輕量模擬 argparse.Namespace。"""
    def __init__(self, **kwargs):
        for f in ("license", "product", "company", "manufacturer",
                  "reagent", "keyword", "qsd", "leaflet"):
            setattr(self, f, kwargs.get(f))


# ───────────────────────── 純邏輯測試 ─────────────────────────

def test_plan_query_no_flags():
    primary, filters = plan_query(_Args())
    assert primary is None
    assert filters == {}


@pytest.mark.parametrize("field", COMBINABLE_FIELDS)
def test_plan_query_single_flag(field):
    """單一欄位：primary = 該欄位，無 cross filter。"""
    primary, filters = plan_query(_Args(**{field: "X"}))
    assert primary == field
    assert filters == {}


def test_plan_query_priority_order():
    """多欄位時，依 COMBINABLE_FIELDS 順序選 primary。"""
    primary, filters = plan_query(_Args(
        company="A", manufacturer="B", reagent="C", product="D", keyword="E",
    ))
    assert primary == "company"
    assert filters == {"manufacturer": "B", "reagent": "C", "product": "D", "keyword": "E"}


@pytest.mark.parametrize("a,b,expected_primary", [
    ("company", "manufacturer", "company"),
    ("company", "reagent", "company"),
    ("company", "product", "company"),
    ("company", "keyword", "company"),
    ("manufacturer", "reagent", "manufacturer"),
    ("manufacturer", "product", "manufacturer"),
    ("manufacturer", "keyword", "manufacturer"),
    ("reagent", "product", "reagent"),
    ("reagent", "keyword", "reagent"),
    ("product", "keyword", "product"),
])
def test_plan_query_pairwise(a, b, expected_primary):
    """所有 2-flag 組合（C(5,2)=10 種）。"""
    args = _Args(**{a: "A", b: "B"})
    primary, filters = plan_query(args)
    assert primary == expected_primary
    other = a if expected_primary == b else b
    assert filters == {other: args.__dict__[other]}


@pytest.mark.parametrize("combo", list(itertools.combinations(COMBINABLE_FIELDS, 3)))
def test_plan_query_triple_combinations(combo):
    """所有 3-flag 組合（C(5,3)=10 種），primary = 優先順序最高者。"""
    values = {f: f"val_{f}" for f in combo}
    args = _Args(**values)
    primary, filters = plan_query(args)
    assert primary == combo[0]  # COMBINABLE_FIELDS 本身即優先序
    assert filters == {f: values[f] for f in combo[1:]}


def test_plan_query_empty_string_ignored():
    """空字串不算有值（argparse 預設是 None，但防禦性檢查）。"""
    primary, filters = plan_query(_Args(company="", manufacturer="ARKRAY"))
    assert primary == "manufacturer"
    assert filters == {}


def test_plan_query_no_dead_primary_attr():
    """驗證 plan_query 不依賴舊版的 args._primary 這類 hack。"""
    args = _Args(company="醫兆", manufacturer="ARKRAY")
    # 刻意不設 _primary；舊版 dead code 會讀 getattr(args, '_primary', None)
    primary, filters = plan_query(args)
    assert primary == "company"
    assert filters == {"manufacturer": "ARKRAY"}


# ───────────────────────── 整合：實際查詢行為 ─────────────────────────

def test_single_company_query_regression(normalized_license_rows):
    """回歸：純 --company 醫兆 單條件查詢結果筆數與修改前一致。"""
    results = search_by_company(normalized_license_rows, "醫兆")
    assert len(results) >= 7  # fixture 內醫兆共 7 筆（不含註銷那 1 筆的 8 筆）


def test_cross_filter_company_and_manufacturer(normalized_license_rows):
    """公司×製造廠組合：醫兆 × ARKRAY 應得 ≥4 筆（試劑 2、儀器 1、校正 1、QC 1）。"""
    from tfda_normalize import get_field
    primary_results = search_by_company(normalized_license_rows, "醫兆")
    filtered = apply_cross_filter(primary_results, manufacturer="ARKRAY")
    assert len(filtered) >= 4
    for row, _ in filtered:
        assert "醫兆" in get_field(row, "company_name", "")
        assert "ARKRAY" in get_field(row, "manufacturer", "")


def test_cross_filter_three_way(normalized_license_rows):
    """三重組合不 crash 且為 AND：醫兆 × ARKRAY × HbA1c → 僅 HbA1c 試劑 1 筆。"""
    primary_results = search_by_company(normalized_license_rows, "醫兆")
    filtered = apply_cross_filter(
        primary_results, manufacturer="ARKRAY", reagent="HbA1c"
    )
    assert len(filtered) >= 1
    for row, _ in filtered:
        combined = " ".join([
            row.get("中文品名", ""), row.get("英文品名", ""),
            row.get("醫器規格", ""), row.get("效能", ""),
        ])
        assert "hba1c" in combined.lower() or "糖化" in combined


def test_cross_filter_product(normalized_license_rows):
    """新增：product 作為 cross filter 可篩。"""
    from tfda_search import search_by_company
    results = search_by_company(normalized_license_rows, "亞培")
    filtered = apply_cross_filter(results, product="Glucose Meter")
    assert len(filtered) >= 1


def test_cross_filter_keyword(normalized_license_rows):
    """新增：keyword 作為 cross filter 可做全文 AND。"""
    from tfda_search import search_by_company
    results = search_by_company(normalized_license_rows, "醫兆")
    filtered = apply_cross_filter(results, keyword="尿液")
    assert len(filtered) >= 1
    for row, _ in filtered:
        from tfda_normalize import get_searchable_text
        assert "尿液" in get_searchable_text(row)
