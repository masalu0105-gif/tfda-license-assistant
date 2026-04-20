"""P3.3 「是不是要查 XXX」打錯字建議驗收。

- distinct_field_values 取 distinct 候選集
- suggest_similar 純函式回傳接近字串
- 效能：200ms 內完成 5000 筆候選的 fuzzy 比對
- 整合：CLI 0 筆時印建議
"""

import time

from tfda_search import (
    distinct_field_values,
    suggest_similar,
)


# ───── distinct_field_values ─────

def test_distinct_companies(normalized_license_rows):
    companies = distinct_field_values(normalized_license_rows, "company_name")
    assert "醫兆科技股份有限公司" in companies
    assert "亞培股份有限公司" in companies
    # 去重
    assert len(companies) == len(set(companies))


def test_distinct_manufacturers(normalized_license_rows):
    mfgs = distinct_field_values(normalized_license_rows, "manufacturer")
    assert "ARKRAY Inc." in mfgs
    assert "Sysmex Corporation" in mfgs


def test_distinct_empty_skipped():
    rows = [{"company_name": "A"}, {"company_name": ""}, {"company_name": "N/A"}]
    out = distinct_field_values(rows, "company_name")
    assert out == ["A"]


# ───── suggest_similar 純函式 ─────

def test_suggest_typo_medizheng(normalized_license_rows):
    """輸入「醫趙」應建議「醫兆科技股份有限公司」。"""
    companies = distinct_field_values(normalized_license_rows, "company_name")
    suggestions = suggest_similar("醫趙", companies, n=3, cutoff=0.5)
    # 至少一個含「醫兆」
    assert any("醫兆" in s for s in suggestions), f"未建議醫兆，實得：{suggestions}"


def test_suggest_english_typo(normalized_license_rows):
    """輸入「ARKRAI」應建議「ARKRAY Inc.」。"""
    mfgs = distinct_field_values(normalized_license_rows, "manufacturer")
    suggestions = suggest_similar("ARKRAI", mfgs, n=3, cutoff=0.6)
    assert any("ARKRAY" in s for s in suggestions), f"未建議 ARKRAY，實得：{suggestions}"


def test_suggest_no_close_match_returns_empty(normalized_license_rows):
    """完全不相似的輸入應回空 list。"""
    companies = distinct_field_values(normalized_license_rows, "company_name")
    assert suggest_similar("xyzabc1234567890", companies) == []


def test_suggest_empty_inputs():
    assert suggest_similar("", ["A", "B"]) == []
    assert suggest_similar("anything", []) == []


def test_suggest_limit_n():
    """n=2 時最多回 2 筆。"""
    candidates = ["apple", "apply", "apricot", "ample", "aphid"]
    result = suggest_similar("applf", candidates, n=2, cutoff=0.5)
    assert len(result) <= 2


def test_suggest_halfwidth_normalized():
    """全形輸入應能建議半形候選。"""
    result = suggest_similar("ＡＲＫＲＡＹ", ["ARKRAY", "Sysmex"], n=1, cutoff=0.8)
    assert "ARKRAY" in result


def test_suggest_performance_under_200ms():
    """5000 筆 distinct 候選的 fuzzy 比對應 < 200ms（DoD）。"""
    candidates = [f"Company_{i:04d}_Manufacturing_Taiwan" for i in range(5000)]
    candidates.append("醫兆科技股份有限公司")
    start = time.perf_counter()
    suggest_similar("醫趙", candidates, n=3, cutoff=0.6)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 200, f"耗時 {elapsed_ms:.1f}ms 超過 200ms 預算"
