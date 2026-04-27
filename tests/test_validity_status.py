"""P0.2 驗收測試：`_get_validity_status` 邏輯與閾值。

覆蓋：
- 警示閾值 = 180 天（對齊 SKILL.md，非舊值 90）
- (過期/即將到期/有效) × (is_valid="是"/"否"/空) = 9 個主 case
- 日期格式異常 fallback
- is_valid="否" 對未過期日期的 override
"""

from datetime import datetime, timedelta

import pytest
from tfda_formatter import (
    WARNING_THRESHOLD_DAYS,
    _get_validity_status,
    _parse_valid_date,
)


def test_threshold_is_180_days():
    """警示閾值必須是 180 天（SKILL.md 承諾），不能是舊的 90。"""
    assert WARNING_THRESHOLD_DAYS == 180


def _future(days: int) -> str:
    return (datetime.now() + timedelta(days=days)).strftime("%Y/%m/%d")


def _past(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")


# ───── (過期/即將到期/有效) × (是/否/空) = 9 主 case ─────

@pytest.mark.parametrize("date_str,is_valid,expected", [
    # 過期日期
    (_past(30),   "是", "❌ 已過期"),  # 日期過期勝過 is_valid="是"
    (_past(30),   "否", "❌ 已過期"),
    (_past(30),   "",   "❌ 已過期"),
    # 即將到期（<180 天）
    (_future(90), "是", "⚠️ 即將到期"),
    (_future(90), "否", "❌ 已過期"),  # is_valid=否 override
    (_future(90), "",   "⚠️ 即將到期"),
    # 有效（>180 天）
    (_future(365), "是", "✅ 有效"),
    (_future(365), "否", "❌ 已過期"),  # is_valid=否 override
    (_future(365), "",   "✅ 有效"),
])
def test_matrix(date_str, is_valid, expected):
    assert _get_validity_status(date_str, is_valid) == expected


# ───── 閾值邊界 ─────

def test_exactly_at_threshold_is_warning():
    """剛好 180 天內（179 天）→ 警示。"""
    assert _get_validity_status(_future(179), "是") == "⚠️ 即將到期"


def test_just_beyond_threshold_is_valid():
    """181 天後 → 有效，不再警示。"""
    assert _get_validity_status(_future(181), "是") == "✅ 有效"


def test_old_threshold_no_longer_triggers_warning():
    """91-179 天區間：舊版（90 天）會判有效，新版（180 天）必須警示。
    此測試確保閾值從 90 → 180 的遷移成功。"""
    assert _get_validity_status(_future(100), "") == "⚠️ 即將到期"


# ───── 日期格式異常 fallback ─────

@pytest.mark.parametrize("bad_date", ["", "N/A", "2025.01.01", "abc", None])
def test_unparseable_date_with_is_valid_true(bad_date):
    """日期無法解析但 is_valid=是 → ✅（舊 bug 在此處會回 N/A）。"""
    result = _get_validity_status(bad_date or "", "是")
    assert result == "✅ 有效"


def test_unparseable_date_with_is_valid_false():
    assert _get_validity_status("亂碼", "否") == "❌ 已過期"


def test_all_unknown_returns_na():
    assert _get_validity_status("", "") == "N/A"


# ───── 日期 parser ─────

@pytest.mark.parametrize("date_str", [
    "2025/01/15", "2025-01-15", "20250115",
])
def test_parse_valid_date_supported_formats(date_str):
    assert _parse_valid_date(date_str) == datetime(2025, 1, 15)


@pytest.mark.parametrize("bad", ["", "N/A", "abc", "2025.01.01"])
def test_parse_valid_date_bad_returns_none(bad):
    assert _parse_valid_date(bad) is None


# ───── 回歸：既有「❌ 已過期」標示不變 ─────

def test_already_expired_regression():
    """SKILL.md 行為契約：明顯過期的日期必須回 ❌。"""
    assert _get_validity_status("2020/01/01", "") == "❌ 已過期"
    assert _get_validity_status("2020/01/01", "是") == "❌ 已過期"
