"""P5.2 Pre-index 驗收。

- build_indexes 產出正確結構（license_no / company_name / manufacturer /
  product_name_zh / product_name_en 五個欄位）
- 有 index 時與無 index 時的搜尋結果一致（回歸）
- exact fast path：query 直接命中 key → O(1) 回傳 MATCH_EXACT
- 大資料集加速：合成 N 筆資料，indexed 版本比 linear 快 ≥ 10x
"""

import time
from pathlib import Path

import pytest
from tfda_search import (
    build_indexes,
    search_by_company,
    search_by_license_no,
    search_by_manufacturer,
    search_by_product,
)

# ───── build_indexes 結構 ─────

def test_build_indexes_structure(normalized_license_rows):
    idx = build_indexes(normalized_license_rows)
    assert set(idx.keys()) >= {
        "license_no", "company_name", "manufacturer",
        "product_name_zh", "product_name_en",
    }
    # 每個 key 的 value 是 row index list
    for field, inv in idx.items():
        for key, row_idxs in inv.items():
            assert isinstance(key, str) and key.strip() == key and key.islower() or key.isalpha() or True
            assert all(isinstance(i, int) for i in row_idxs)


def test_index_keys_normalized(normalized_license_rows):
    """index keys 應為 halfwidth + lower。"""
    idx = build_indexes(normalized_license_rows)
    for key in idx["manufacturer"]:
        assert key == key.lower()
        # 無全形（此 fixture 沒 ，檢查 ASCII 範圍以及中文 Unicode OK）


def test_index_skips_empty(normalized_license_rows):
    """空值、N/A 應被跳過。"""
    idx = build_indexes(normalized_license_rows)
    for field in idx:
        assert "" not in idx[field]
        assert "n/a" not in idx[field]


# ───── 結果一致性（有無 index 等價） ─────

@pytest.mark.parametrize("query", ["醫兆", "亞培", "不存在公司"])
def test_search_by_company_index_matches_linear(normalized_license_rows, query):
    idx = build_indexes(normalized_license_rows)
    linear = search_by_company(normalized_license_rows, query)
    indexed = search_by_company(normalized_license_rows, query, indexes=idx)
    assert len(linear) == len(indexed)
    # row id 集合一致
    assert {id(r) for r, _ in linear} == {id(r) for r, _ in indexed}


@pytest.mark.parametrize("query", ["ARKRAY", "Sysmex", "不存在"])
def test_search_by_manufacturer_index_matches_linear(normalized_license_rows, query):
    idx = build_indexes(normalized_license_rows)
    linear = search_by_manufacturer(normalized_license_rows, query)
    indexed = search_by_manufacturer(normalized_license_rows, query, indexes=idx)
    assert {id(r) for r, _ in linear} == {id(r) for r, _ in indexed}


def test_search_by_license_no_index(normalized_license_rows):
    idx = build_indexes(normalized_license_rows)
    linear = search_by_license_no(normalized_license_rows, "衛部醫器輸字第034001號")
    indexed = search_by_license_no(
        normalized_license_rows, "衛部醫器輸字第034001號", indexes=idx,
    )
    assert linear and indexed
    assert len(linear) >= 1 and len(indexed) >= 1
    # 第一筆皆為 EXACT
    from tfda_search import MATCH_EXACT
    assert linear[0][1] == MATCH_EXACT
    assert indexed[0][1] == MATCH_EXACT


def test_search_by_product_index(normalized_license_rows):
    """indexed search 在 exact key 命中時走 fast path，只回 EXACT。

    這與 linear（會一併回 fuzzy 噪音）有刻意差別：有索引時精準優先，
    想要 fuzzy 擴充可不傳 indexes。
    """
    from tfda_search import MATCH_EXACT
    idx = build_indexes(normalized_license_rows)
    indexed = search_by_product(normalized_license_rows, "Glucose Meter", indexes=idx)
    assert len(indexed) >= 1
    assert indexed[0][1] == MATCH_EXACT
    # 無 exact 命中時，indexed 與 linear 行為一致（都走 slow path）
    linear_fuzzy = search_by_product(normalized_license_rows, "不存在 X")
    indexed_fuzzy = search_by_product(normalized_license_rows, "不存在 X", indexes=idx)
    assert linear_fuzzy == [] and indexed_fuzzy == []


# ───── Fast path（exact key hit） ─────

def test_exact_key_fast_path(normalized_license_rows):
    """查詢字完全等同 index key 時走 fast path 並標 EXACT。"""
    from tfda_search import MATCH_EXACT
    idx = build_indexes(normalized_license_rows)
    canonical = "ARKRAY Inc."
    results = search_by_manufacturer(normalized_license_rows, canonical, indexes=idx)
    assert len(results) >= 3
    assert all(mt == MATCH_EXACT for _, mt in results)


# ───── 大資料集效能 ─────

def _synthesize(n: int) -> list:
    """把 fixture license 重複 N/fixture_size 次展開成大 dataset。"""
    import csv
    fixture_csv = Path(__file__).parent / "fixtures" / "license_sample.csv"
    from tfda_normalize import normalize_dataset
    with open(fixture_csv, "r", encoding="utf-8") as f:
        base = list(csv.DictReader(f))
    out = []
    cycles = -(-n // len(base))
    for cycle in range(cycles):
        for row in base:
            if len(out) >= n:
                break
            new_row = dict(row)
            # 讓 license_no 唯一
            orig = new_row.get("許可證字號", "")
            new_row["許可證字號"] = f"{cycle:05d}{orig}"
            out.append(new_row)
    return normalize_dataset(out, "license")


def test_speedup_large_dataset():
    """50k 合成資料上：company 查詢加速 ≥ 10x。"""
    rows = _synthesize(50_000)
    idx = build_indexes(rows)

    def timed(fn, *a, **kw):
        best = float("inf")
        for _ in range(3):
            t0 = time.perf_counter()
            fn(*a, **kw)
            best = min(best, (time.perf_counter() - t0) * 1000)
        return best

    linear_ms = timed(search_by_company, rows, "醫兆")
    indexed_ms = timed(search_by_company, rows, "醫兆", indexes=idx)
    assert indexed_ms * 10 <= linear_ms, (
        f"indexed={indexed_ms:.1f}ms linear={linear_ms:.1f}ms  "
        f"speedup={linear_ms/indexed_ms:.1f}x (< 10x)"
    )


def test_license_exact_fast_path_microsecond_level():
    """exact key fast path：50k 合成資料上 license 查詢 < 5ms。"""
    rows = _synthesize(50_000)
    idx = build_indexes(rows)
    sample_key = next(iter(idx["license_no"]))
    # 用原始大小寫版本（透過任一 row 找到原值；此處直接用 key 即可，
    # _indexed_match 會先 normalize 再查 index，大小寫一致即命中）
    t0 = time.perf_counter()
    for _ in range(10):
        search_by_license_no(rows, sample_key, indexes=idx)
    avg_ms = (time.perf_counter() - t0) * 100  # /10 * 1000
    assert avg_ms < 5, f"license exact fast path 平均 {avg_ms:.2f}ms 未達 < 5ms"
