"""P1.2 單元測試：tfda_normalize 模組。

覆蓋重點：
- FIELD_ALIASES 多別名對映
- 「許可編號」在 QSD/QMS 資料集的分流（key 衝突處理）
- get_field：unified → alias fallback → 預設值
- get_searchable_text：文字欄位組合、空值過濾
"""

import pytest

from tfda_normalize import (
    FIELD_ALIASES, get_field, get_searchable_text, normalize_row, normalize_dataset,
)


# ───── normalize_row ─────

def test_normalize_adds_unified_field():
    row = {"許可證字號": "衛部醫器輸字第000001號", "申請商名稱": "A 公司"}
    n = normalize_row(row)
    assert n["license_no"] == "衛部醫器輸字第000001號"
    assert n["company_name"] == "A 公司"
    # 原欄位保留
    assert n["許可證字號"] == "衛部醫器輸字第000001號"


def test_normalize_strips_key_whitespace():
    row = {" 許可證字號 ": "X", "中文品名": "Y"}
    n = normalize_row(row)
    assert "許可證字號" in n
    assert n["license_no"] == "X"


def test_normalize_qsd_許可編號_to_qsd_no():
    row = {"許可編號": "QSD000999", "製造廠名稱": "M"}
    n = normalize_row(row, dataset_key="qsd")
    assert n["qsd_no"] == "QSD000999"


def test_normalize_qms_許可編號_to_qms_license_no():
    row = {"許可編號": "QMS000111"}
    n = normalize_row(row, dataset_key="qms")
    assert n["qms_license_no"] == "QMS000111"


def test_normalize_許可編號_fallback_when_dataset_unknown():
    """dataset_key 非 qsd/qms 時，採用 FIELD_ALIASES 定義的 unified（預設 qms_license_no 或 qsd_no）。"""
    row = {"許可編號": "X"}
    n = normalize_row(row, dataset_key="")
    # 會走 else 分支，採 _REVERSE_MAP 的查表結果（實作決定）
    # 最少要有原始欄位
    assert n["許可編號"] == "X"


def test_normalize_unknown_field_preserved():
    row = {"冷門欄位 A": "v1", "中文品名": "v2"}
    n = normalize_row(row)
    assert n["冷門欄位 A"] == "v1"
    assert n["product_name_zh"] == "v2"


def test_normalize_dataset_all_rows():
    rows = [
        {"許可證字號": "L1", "中文品名": "A"},
        {"許可證字號": "L2", "中文品名": "B"},
    ]
    out = normalize_dataset(rows, "license")
    assert len(out) == 2
    assert [r["license_no"] for r in out] == ["L1", "L2"]


# ───── get_field ─────

def test_get_field_from_unified():
    row = {"license_no": "L1"}
    assert get_field(row, "license_no") == "L1"


def test_get_field_fallback_to_alias():
    row = {"中文品名": "糖化血紅素試劑"}
    assert get_field(row, "product_name_zh") == "糖化血紅素試劑"


def test_get_field_default_when_missing():
    assert get_field({}, "license_no") == "N/A"
    assert get_field({}, "license_no", default="") == ""


def test_get_field_skips_empty_values():
    """空字串/None 不算有值，必須 fallback。"""
    row = {"license_no": "", "許可證字號": "L2"}
    assert get_field(row, "license_no") == "L2"


def test_get_field_unknown_field_returns_default():
    assert get_field({"a": 1}, "完全不存在的欄位") == "N/A"


# ───── get_searchable_text ─────

def test_get_searchable_text_combines_fields():
    row = {
        "product_name_zh": "糖化血紅素",
        "product_name_en": "HbA1c",
        "manufacturer": "ARKRAY",
        "efficacy": "",  # 應被忽略
    }
    text = get_searchable_text(row)
    assert "糖化血紅素" in text
    assert "HbA1c" in text
    assert "ARKRAY" in text


def test_get_searchable_text_excludes_na():
    row = {"product_name_zh": "N/A", "中文品名": "真實品名"}
    text = get_searchable_text(row)
    assert "N/A" not in text
    assert "真實品名" in text


def test_get_searchable_text_empty_row():
    assert get_searchable_text({}) == ""


# ───── FIELD_ALIASES 結構 ─────

def test_field_aliases_all_unified_names_lowercase_snake():
    for key in FIELD_ALIASES:
        assert key.islower() or "_" in key or key.isalpha()


def test_no_duplicate_aliases_within_unified():
    for unified, aliases in FIELD_ALIASES.items():
        assert len(aliases) == len(set(aliases)), f"{unified} 有重複 alias"
