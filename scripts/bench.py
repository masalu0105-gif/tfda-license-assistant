#!/usr/bin/env python3
"""TFDA query benchmark — P5.1 baseline。

用法：
  # 跑目前 ~/.cache/tfda/*.csv 的 baseline
  python scripts/bench.py

  # 自產合成資料跑（無需真實快取；可指定筆數）
  python scripts/bench.py --synthetic 150000

  # 指定輸出路徑
  python scripts/bench.py --output docs/bench-results.md

量測兩類數據：
  cold_load_ms：load_dataset + normalize_dataset（CLI 啟動成本）
  per_query_ms：各 scenario 重複 5 次的 p50 / p95（搜尋本身）

baseline 產出 markdown 表格；後續 P5.2/P5.3 的「是否需要做」
依據此表決定：
  - per_query_ms.p50 > 500ms → 做 P5.2 pre-index
  - cold_load_ms > 1000ms → 做 P5.3 normalize 快取
"""

import argparse
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tfda_datasets import load_dataset  # noqa: E402
from tfda_normalize import normalize_dataset  # noqa: E402
from tfda_search import (  # noqa: E402
    apply_cross_filter,
    search_by_company,
    search_by_keyword,
    search_by_license_no,
    search_by_manufacturer,
    search_by_product,
    search_by_reagent,
)

SCENARIOS: List[Tuple[str, Callable]] = [
    ("company__醫兆",          lambda rows: search_by_company(rows, "醫兆")),
    ("manufacturer__ARKRAY",   lambda rows: search_by_manufacturer(rows, "ARKRAY")),
    ("manufacturer__Sysmex",   lambda rows: search_by_manufacturer(rows, "Sysmex")),
    ("reagent__HbA1c",         lambda rows: search_by_reagent(rows, "HbA1c")),
    ("keyword__尿液",          lambda rows: search_by_keyword(rows, "尿液")),
    ("product__Glucose",       lambda rows: search_by_product(rows, "Glucose")),
    ("license__exact",         lambda rows: search_by_license_no(rows, "衛部醫器輸字第034001號")),
    ("cross_filter__3way",     lambda rows: apply_cross_filter(
        search_by_company(rows, "醫兆"),
        manufacturer="ARKRAY", reagent="HbA1c",
    )),
]


def _build_synthetic_cache(out_dir: Path, target_rows: int) -> Path:
    """從 fixture 倍擴展出 target_rows 筆合成資料，寫到 out_dir/license.csv。"""
    fixtures = Path(__file__).parent.parent / "tests" / "fixtures"
    src = fixtures / "license_sample.csv"
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / "license.csv"
    with open(src, "r", encoding="utf-8") as f:
        lines = f.readlines()
    header, data_lines = lines[0], lines[1:]
    needed_cycles = -(-target_rows // len(data_lines))  # ceil
    with open(dst, "w", encoding="utf-8") as f:
        f.write(header)
        written = 0
        for cycle in range(needed_cycles):
            for line in data_lines:
                if written >= target_rows:
                    break
                # 讓每筆 license_no 唯一
                mutated = line.replace(
                    "衛部醫器輸字第",
                    f"衛部醫器輸字第{cycle:05d}",
                    1,
                )
                f.write(mutated)
                written += 1
    # 寫最小 meta
    import json
    from datetime import datetime
    meta = {
        "downloaded_at": datetime.now().isoformat(),
        "source_url": "synthetic://license",
        "info_id": 68,
        "dataset_name": "醫療器材許可證 (synthetic)",
    }
    with open(out_dir / "license_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return dst


def run_bench(rows, repeats: int = 5) -> Dict[str, Dict[str, float]]:
    """對 rows 跑所有 scenarios，回傳 {name: {p50, p95, n_hits}}。"""
    results = {}
    for name, fn in SCENARIOS:
        timings = []
        hits = 0
        for _ in range(repeats):
            t0 = time.perf_counter()
            out = fn(rows)
            timings.append((time.perf_counter() - t0) * 1000)
            hits = len(out)
        timings.sort()
        results[name] = {
            "p50_ms": round(statistics.median(timings), 2),
            "p95_ms": round(timings[min(int(0.95 * repeats), repeats - 1)], 2),
            "n_hits": hits,
        }
    return results


def format_report(
    cold_load_ms: float,
    query_results: Dict[str, Dict[str, float]],
    source: str,
    row_count: int,
) -> str:
    lines = []
    lines.append("# TFDA bench baseline\n")
    lines.append(f"- source: {source}")
    lines.append(f"- rows: {row_count}")
    lines.append(f"- cold_load_ms: {cold_load_ms:.1f}")
    lines.append("")
    lines.append("| scenario | p50 (ms) | p95 (ms) | n_hits |")
    lines.append("|---|---:|---:|---:|")
    for name, m in query_results.items():
        lines.append(f"| {name} | {m['p50_ms']} | {m['p95_ms']} | {m['n_hits']} |")
    lines.append("")
    # P5.2 / P5.3 觸發判定
    slow = [n for n, m in query_results.items() if m["p50_ms"] > 500]
    cold_slow = cold_load_ms > 1000
    lines.append("## 結論")
    lines.append("- P5.2 pre-index 觸發：" + ("**需要**（" + ", ".join(slow) + "）" if slow else "不需要"))
    lines.append("- P5.3 normalize 快取觸發：" + ("**需要**" if cold_slow else "不需要"))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="TFDA query benchmark")
    parser.add_argument("--synthetic", type=int, default=0,
                        help="生成合成資料的筆數（預設 0 = 使用既有 cache）")
    parser.add_argument("--output", type=str, default="",
                        help="把 markdown 報告寫到指定檔案（預設 print 到 stdout）")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    if args.synthetic > 0:
        import tempfile

        import tfda_datasets
        tmp = Path(tempfile.mkdtemp(prefix="tfda_bench_"))
        _build_synthetic_cache(tmp, args.synthetic)
        tfda_datasets.CACHE_DIR = tmp
        source = f"synthetic@{tmp}"
    else:
        source = "real cache ~/.cache/tfda"

    # Cold load
    t0 = time.perf_counter()
    data = load_dataset("license")
    normalized = normalize_dataset(data, "license")
    cold_ms = (time.perf_counter() - t0) * 1000

    # Per-query
    query_results = run_bench(normalized, repeats=args.repeats)
    report = format_report(cold_ms, query_results, source=source, row_count=len(normalized))

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Written: {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
