"""P1.2 單元測試：tfda_search 模組。

覆蓋：
- 所有 search_by_* 函式的 exact / contains / fuzzy 匹配
- _match_value、_best_match、_sort_results 私有函式
- search_qsd、search_leaflet 的兩種輸入型態
- 匹配優先序：exact > contains > fuzzy
"""


from tfda_search import (
    MATCH_CONTAINS,
    MATCH_EXACT,
    MATCH_FUZZY,
    _best_match,
    _match_value,
    _sort_results,
    apply_cross_filter,
    plan_query,
    search_by_company,
    search_by_keyword,
    search_by_license_no,
    search_by_manufacturer,
    search_by_product,
    search_by_reagent,
    search_leaflet,
    search_qsd,
)

# ───── _match_value ─────

def test_match_value_exact():
    assert _match_value("ABC", "ABC") == MATCH_EXACT
    assert _match_value("醫兆", "醫兆") == MATCH_EXACT


def test_match_value_case_insensitive_exact():
    assert _match_value("abc", "ABC") == MATCH_EXACT


def test_match_value_contains():
    assert _match_value("ARKRAY", "ARKRAY Inc.") == MATCH_CONTAINS
    assert _match_value("醫兆", "醫兆科技股份有限公司") == MATCH_CONTAINS


def test_match_value_reverse_contains():
    """query 比 value 長時也算 contains（query 包含 value）。"""
    assert _match_value("ARKRAY Inc.", "ARKRAY") == MATCH_CONTAINS


def test_match_value_fuzzy():
    # difflib 對英文表現較好
    mt = _match_value("ARKREY", "ARKRAY", fuzzy_cutoff=0.5)
    assert mt == MATCH_FUZZY


def test_match_value_no_match():
    assert _match_value("ABCDEF", "XYZ123") is None


def test_match_value_empty():
    assert _match_value("", "anything") is None
    assert _match_value("x", "") is None


# ───── _best_match / _sort_results ─────

def test_best_match_priority():
    assert _best_match(MATCH_EXACT, MATCH_CONTAINS) == MATCH_EXACT
    assert _best_match(MATCH_CONTAINS, MATCH_FUZZY) == MATCH_CONTAINS
    assert _best_match(None, MATCH_FUZZY) == MATCH_FUZZY
    assert _best_match(None, None) is None


def test_sort_results_priority():
    items = [
        ({"id": 1}, MATCH_FUZZY),
        ({"id": 2}, MATCH_EXACT),
        ({"id": 3}, MATCH_CONTAINS),
    ]
    sorted_ = _sort_results(items)
    assert [r[0]["id"] for r in sorted_] == [2, 3, 1]


# ───── search_by_license_no ─────

def test_search_by_license_no_exact(normalized_license_rows):
    hits = search_by_license_no(normalized_license_rows, "衛部醫器輸字第034001號")
    assert hits
    assert hits[0][1] == MATCH_EXACT


def test_search_by_license_no_zero(normalized_license_rows):
    hits = search_by_license_no(normalized_license_rows, "不存在的許可證號碼")
    assert hits == []


# ───── search_by_company ─────

def test_search_by_company_contains(normalized_license_rows):
    hits = search_by_company(normalized_license_rows, "醫兆")
    assert len(hits) >= 7
    assert all(h[1] in (MATCH_EXACT, MATCH_CONTAINS) for h in hits)


def test_search_by_company_zero(normalized_license_rows):
    hits = search_by_company(normalized_license_rows, "不存在公司 XYZ")
    assert hits == []


# ───── search_by_manufacturer ─────

def test_search_by_manufacturer_lower_fuzzy_cutoff(normalized_license_rows):
    """製造廠用放寬的 fuzzy cutoff 0.4。"""
    hits = search_by_manufacturer(normalized_license_rows, "ARKRAY")
    assert len(hits) >= 4


# ───── search_by_product / reagent / keyword ─────

def test_search_by_product_chinese(normalized_license_rows):
    hits = search_by_product(normalized_license_rows, "糖化血紅素")
    assert len(hits) >= 1


def test_search_by_product_english(normalized_license_rows):
    hits = search_by_product(normalized_license_rows, "Glucose Meter")
    assert len(hits) >= 1


def test_search_by_reagent_multi_field(normalized_license_rows):
    """reagent 會搜尋品名 + 效能 + 規格多欄位。"""
    hits = search_by_reagent(normalized_license_rows, "HbA1c")
    assert len(hits) >= 2


def test_search_by_keyword_fulltext(normalized_license_rows):
    hits = search_by_keyword(normalized_license_rows, "尿液")
    assert len(hits) >= 2


def test_search_by_keyword_case_insensitive(normalized_license_rows):
    hits_upper = search_by_keyword(normalized_license_rows, "ARKRAY")
    hits_lower = search_by_keyword(normalized_license_rows, "arkray")
    assert len(hits_upper) == len(hits_lower)


# ───── search_qsd ─────

def test_search_qsd_by_company(normalized_qsd_rows):
    hits = search_qsd(normalized_qsd_rows, "醫兆")
    assert len(hits) >= 2


def test_search_qsd_by_manufacturer(normalized_qsd_rows):
    hits = search_qsd(normalized_qsd_rows, "ARKRAY")
    assert len(hits) >= 1


def test_search_qsd_zero(normalized_qsd_rows):
    assert search_qsd(normalized_qsd_rows, "XYZ 不存在") == []


# ───── search_leaflet ─────

def test_search_leaflet_by_license_no(normalized_leaflet_rows):
    """輸入許可證字號樣貌 → 從 license_no 欄搜尋。

    已知問題：許可證字號用 _match_value 會 fuzzy 命中相似號碼，
    首筆為 MATCH_EXACT 但後續可能含雜訊。待後續專案修（改為
    exact+contains only）。此處先驗證 MATCH_EXACT 必為首筆。
    """
    hits = search_leaflet(normalized_leaflet_rows, "衛部醫器輸字第034001號")
    assert len(hits) >= 1
    assert hits[0][1] == MATCH_EXACT
    assert "034001" in hits[0][0].get("license_no", "")


def test_search_leaflet_by_product_name(normalized_leaflet_rows):
    """輸入產品名（非許可證字號樣貌）→ 從品名欄搜尋。"""
    hits = search_leaflet(normalized_leaflet_rows, "糖化血紅素")
    assert len(hits) >= 1


# ───── apply_cross_filter 邊界 ─────

def test_apply_cross_filter_no_filters_returns_same(normalized_license_rows):
    results = search_by_company(normalized_license_rows, "醫兆")
    filtered = apply_cross_filter(results)
    assert len(filtered) == len(results)


def test_apply_cross_filter_chain_shrinks(normalized_license_rows):
    results = search_by_company(normalized_license_rows, "醫兆")
    one_filter = apply_cross_filter(results, manufacturer="ARKRAY")
    two_filter = apply_cross_filter(one_filter, reagent="HbA1c")
    assert len(two_filter) <= len(one_filter) <= len(results)


# ───── plan_query 邊界（額外補 test_cli_dispatch 未覆蓋處） ─────

def test_plan_query_keyword_only():
    class A:
        company = None
        manufacturer = None
        reagent = None
        product = None
        keyword = "尿液"
    p, f = plan_query(A())
    assert p == "keyword"
    assert f == {}
