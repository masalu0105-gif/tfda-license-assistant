"""Fixture 健檢：確認 fixture 可載入、normalize 成功、隔離快取有效。"""

from pathlib import Path


def test_license_rows_loaded(license_rows):
    assert len(license_rows) >= 20
    assert "許可證字號" in license_rows[0]


def test_qsd_rows_loaded(qsd_rows):
    assert len(qsd_rows) >= 6
    assert "許可編號" in qsd_rows[0]


def test_leaflet_rows_loaded(leaflet_rows):
    assert len(leaflet_rows) >= 6
    assert "說明書圖檔連結" in leaflet_rows[0]


def test_normalize_license(normalized_license_rows):
    row = normalized_license_rows[0]
    assert row.get("license_no") == "衛部醫器輸字第034001號"
    assert row.get("company_name") == "醫兆科技股份有限公司"
    assert row.get("manufacturer") == "ARKRAY Inc."


def test_normalize_qsd_許可編號_splits_correctly(normalized_qsd_rows):
    """QSD/QMS 的「許可編號」撞名處理：dataset_key='qsd' 時應對映到 qsd_no。"""
    row = normalized_qsd_rows[0]
    assert row.get("qsd_no") == "QSD000123"


def test_isolated_cache_is_tmp(isolated_cache, tmp_path):
    """確認測試用的 CACHE_DIR 在 tmp_path 下，不會碰到使用者家目錄。

    用 str.startswith 而非 Path.is_relative_to（後者 Python 3.9+ 才支援）。
    """
    assert str(Path(isolated_cache)).startswith(str(tmp_path))
    import tfda_datasets
    assert tfda_datasets.CACHE_DIR == isolated_cache


def test_no_pii_in_fixture(license_rows):
    """去敏自檢：統編都是遞增 8 位數 12345678 系列，地址都含『測試路』。"""
    for row in license_rows:
        addr = row.get("申請商地址", "")
        if addr:
            assert "測試路" in addr, f"未去敏的地址：{addr}"
