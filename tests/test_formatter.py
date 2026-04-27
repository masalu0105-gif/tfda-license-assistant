"""P1.2 單元測試：tfda_formatter 模組。

覆蓋：
- format_license_table：空結果、limit 生效、表格欄位齊全
- format_grouped_by_manufacturer：分組統計、limit 截斷
- format_leaflet_table、format_qsd_table、format_json、format_summary
- format_cache_footer 的 cached / 未 cached 分支
- _field_label 各別標籤
"""

import json

from tfda_formatter import (
    _field_label,
    format_cache_footer,
    format_grouped_by_manufacturer,
    format_json,
    format_leaflet_table,
    format_license_table,
    format_qsd_table,
    format_summary,
)
from tfda_search import (
    MATCH_EXACT,
    search_by_company,
    search_leaflet,
    search_qsd,
)

# ───── format_license_table ─────

def test_format_license_table_empty():
    assert "未找到" in format_license_table([])


def test_format_license_table_contains_headers(normalized_license_rows):
    hits = search_by_company(normalized_license_rows, "醫兆")
    out = format_license_table(hits)
    assert "| 許可證字號" in out
    assert "| 中文品名" in out
    assert "醫兆" in out


def test_format_license_table_respects_limit(normalized_license_rows):
    hits = search_by_company(normalized_license_rows, "醫兆")
    assert len(hits) > 3
    out = format_license_table(hits, limit=3)
    assert "僅顯示前 3 筆" in out


def test_format_license_table_no_truncate_notice_when_under_limit(normalized_license_rows):
    hits = search_by_company(normalized_license_rows, "亞培")
    out = format_license_table(hits, limit=100)
    assert "僅顯示前" not in out


# ───── format_grouped_by_manufacturer ─────

def test_format_grouped_empty():
    assert "未找到" in format_grouped_by_manufacturer([])


def test_format_grouped_shows_distribution(normalized_license_rows):
    hits = search_by_company(normalized_license_rows, "醫兆")
    out = format_grouped_by_manufacturer(hits)
    assert "製造廠分布" in out
    assert "ARKRAY" in out or "Sysmex" in out


def test_format_grouped_limit_truncation(normalized_license_rows):
    hits = search_by_company(normalized_license_rows, "醫兆")
    out = format_grouped_by_manufacturer(hits, limit=1)
    assert "已達顯示上限" in out


# ───── format_leaflet_table ─────

def test_format_leaflet_empty():
    assert "未找到仿單" in format_leaflet_table([])


def test_format_leaflet_renders_links(normalized_leaflet_rows):
    hits = search_leaflet(normalized_leaflet_rows, "衛部醫器輸字第034001號")
    out = format_leaflet_table(hits)
    assert "[查看]" in out
    assert "fake034001_leaflet" in out


def test_format_leaflet_na_for_missing_url(normalized_leaflet_rows):
    """樣本 034002 沒有外盒連結 → 應顯示 N/A。"""
    hits = search_leaflet(normalized_leaflet_rows, "衛部醫器輸字第034002號")
    out = format_leaflet_table(hits)
    assert "N/A" in out


# ───── format_qsd_table ─────

def test_format_qsd_empty():
    assert "未找到 QSD" in format_qsd_table([])


def test_format_qsd_contains_validity_markers(normalized_qsd_rows):
    hits = search_qsd(normalized_qsd_rows, "醫兆")
    out = format_qsd_table(hits)
    assert "| 許可編號" in out
    # fixture 裡有「是」「否」兩種：至少有一個狀態標示
    assert "❌" in out or "⚠️" in out or "✅" in out


# ───── format_json ─────

def test_format_json_includes_match_type(normalized_license_rows):
    hits = search_by_company(normalized_license_rows, "醫兆")[:2]
    out = format_json(hits)
    data = json.loads(out)
    assert len(data) == 2
    assert "_match_type" in data[0]


def test_format_json_valid_utf8():
    row = {"中文品名": "糖化血紅素"}
    out = format_json([(row, MATCH_EXACT)])
    assert "糖化血紅素" in out  # 不被 escape


# ───── format_summary ─────

def test_format_summary_empty():
    assert "無資料" in format_summary([])


def test_format_summary_by_manufacturer(normalized_license_rows):
    hits = search_by_company(normalized_license_rows, "醫兆")
    out = format_summary(hits, "manufacturer")
    assert "依製造廠分組" in out
    assert ":" in out or "：" in out


def test_format_summary_top_10_plus_others():
    """> 10 組時，應合併「其他 N 個」。"""
    rows = [
        ({"manufacturer": f"M{i:03d}"}, MATCH_EXACT) for i in range(15)
    ]
    out = format_summary(rows, "manufacturer")
    assert "其他" in out


# ───── format_cache_footer ─────

def test_format_cache_footer_with_cache():
    info = {
        "license": {"name": "醫療器材許可證", "cached": True,
                    "cache_date": "2026-04-20", "valid": True},
    }
    out = format_cache_footer(info)
    assert "醫療器材許可證" in out
    assert "2026-04-20" in out


def test_format_cache_footer_no_cache():
    info = {"license": {"name": "X", "cached": False, "cache_date": None, "valid": False}}
    out = format_cache_footer(info)
    assert "資料來源：TFDA 開放資料" in out


# ───── _field_label ─────

def test_field_label_known():
    assert _field_label("manufacturer") == "製造廠"
    assert _field_label("company_name") == "申請商"


def test_field_label_unknown_returns_raw():
    assert _field_label("unknown_field") == "unknown_field"
