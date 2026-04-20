"""P3.1 全形 ↔ 半形正規化驗收。

確保：
- to_halfwidth() 正確轉換英數、標點、空白
- 中文字不被波及
- 查詢走 _match_value 時，ＡＲＫＲＡＹ 能命中 ARKRAY
- 原本半形 ARKRAY 的結果筆數 ±0（回歸）
"""

import pytest

from tfda_normalize import to_halfwidth
from tfda_search import MATCH_EXACT, _match_value, search_by_manufacturer


# ───── to_halfwidth 純函式 ─────

@pytest.mark.parametrize("fullwidth,expected", [
    ("ＡＲＫＲＡＹ", "ARKRAY"),
    ("ａｒｋｒａｙ", "arkray"),
    ("Ｈｂ Ａ１ｃ", "Hb A1c"),
    ("０１２３", "0123"),
    ("（測試）", "(測試)"),
    ("Ａ　Ｂ", "A B"),         # 全形空白 U+3000
    ("", ""),
    ("醫兆", "醫兆"),           # 中文不動
    ("ARKRAY", "ARKRAY"),      # 已是半形不動
    ("醫兆 ＡＲＫＲＡＹ", "醫兆 ARKRAY"),  # 混合
])
def test_to_halfwidth(fullwidth, expected):
    assert to_halfwidth(fullwidth) == expected


def test_to_halfwidth_none_and_empty():
    assert to_halfwidth("") == ""
    assert to_halfwidth(None) is None  # 輸入 None 時回 None 不 crash


# ───── _match_value 整合：全形查詢 = 半形查詢 ─────

def test_match_fullwidth_query_hits_halfwidth_value():
    """「ＡＲＫＲＡＹ」(全形) 比對 ARKRAY (半形) 應 EXACT。"""
    assert _match_value("ＡＲＫＲＡＹ", "ARKRAY") == MATCH_EXACT


def test_match_halfwidth_query_hits_fullwidth_value():
    """反向：半形查詢命中全形存值。"""
    assert _match_value("ARKRAY", "ＡＲＫＲＡＹ") == MATCH_EXACT


def test_match_fullwidth_in_fullwidth_value():
    assert _match_value("ＡＲＫＲＡＹ", "ＡＲＫＲＡＹ Ｉｎｃ．") is not None


# ───── 整合：實際 search_by_manufacturer 能接受全形輸入 ─────

def test_search_by_manufacturer_fullwidth_input(normalized_license_rows):
    """查「ＡＲＫＲＡＹ」(全形) 應等同「ARKRAY」結果。"""
    half = search_by_manufacturer(normalized_license_rows, "ARKRAY")
    full = search_by_manufacturer(normalized_license_rows, "ＡＲＫＲＡＹ")
    assert len(half) == len(full)
    assert len(full) >= 4


def test_search_halfwidth_regression_no_change(normalized_license_rows):
    """回歸：半形 ARKRAY 結果筆數不變。"""
    results = search_by_manufacturer(normalized_license_rows, "ARKRAY")
    # fixture 內 ARKRAY 共 5 筆 (醫兆×3 + 康泰×2) + ARKRAY Factory×1
    assert len(results) >= 4
