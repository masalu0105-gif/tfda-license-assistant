#!/usr/bin/env python3
"""TFDA 醫療器材資料查詢工具 — CLI 入口。

用法：
  python query_tfda.py --company "醫兆"
  python query_tfda.py --manufacturer "ARKRAY"
  python query_tfda.py --reagent "HbA1c"
  python query_tfda.py --license "衛部醫器輸字第XXXXXX號"
  python query_tfda.py --company "醫兆" --manufacturer "ARKRAY"
  python query_tfda.py --update-cache
"""

import argparse
import logging
import os
import sys
import time
from typing import Optional

# 確保可以 import 同目錄模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tfda_datasets import get_cache_info, load_dataset, update_all_cache  # noqa: E402
from tfda_formatter import (  # noqa: E402
    format_cache_footer,
    format_grouped_by_manufacturer,
    format_json,
    format_leaflet_table,
    format_license_table,
    format_qsd_table,
    format_summary,
)
from tfda_metrics import record as record_metric  # noqa: E402
from tfda_normalize import get_field, normalize_dataset  # noqa: E402
from tfda_search import (  # noqa: E402
    apply_cross_filter,
    distinct_field_values,
    plan_query,
    search_by_company,
    search_by_keyword,
    search_by_license_no,
    search_by_manufacturer,
    search_by_product,
    search_by_reagent,
    search_company_with_alias,
    search_leaflet,
    search_manufacturer_with_alias,
    search_qsd,
    suggest_similar,
)

# Progress / 提示訊息走 logger（預設輸出到 stderr）；
# 實際結果（表格、JSON、count）走 print() 到 stdout，方便下游 pipe。
log = logging.getLogger("tfda")


def _configure_logging(quiet: bool, verbose: bool) -> None:
    """設定 logging level 與 handler。

    - 預設：INFO（「正在查詢...」「提示：...」等進度訊息印到 stderr）
    - --quiet：ERROR（只印錯誤）
    - --verbose：DEBUG
    stdout 的結果輸出不受 logging level 影響。
    """
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    # 移除舊 handler（避免 test 多次呼叫時疊加）
    for h in list(log.handlers):
        log.removeHandler(h)
    log.addHandler(handler)
    log.setLevel(level)
    log.propagate = False

# primary 欄位 → 對應 distinct 欄位（用於 typo suggestion）
_SUGGEST_FIELD_MAP = {
    "company": "company_name",
    "manufacturer": "manufacturer",
}

# Primary field → (搜尋函式, 是否支援 alias fallback)
# 支援 alias 的 wrapper 回傳 (results, alias_used)，其餘直接回 results。
_PRIMARY_SEARCH = {
    "company": search_by_company,
    "manufacturer": search_by_manufacturer,
    "reagent": search_by_reagent,
    "product": search_by_product,
    "keyword": search_by_keyword,
}

_ALIAS_AWARE_SEARCH = {
    "company": search_company_with_alias,
    "manufacturer": search_manufacturer_with_alias,
}


def _field_label_zh(field: str) -> str:
    """primary/filter 欄位的中文標籤（僅用於 log）。"""
    return {
        "company": "公司",
        "manufacturer": "製造廠",
        "reagent": "試劑",
        "product": "產品",
        "keyword": "關鍵字",
    }.get(field, field)


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI 參數解析器。"""
    parser = argparse.ArgumentParser(
        description="TFDA 醫療器材資料查詢工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  python query_tfda.py --company "醫兆"
  python query_tfda.py --company "醫兆" --manufacturer "ARKRAY"
  python query_tfda.py --reagent "HbA1c"
  python query_tfda.py --license "衛部醫器輸字第000001號"
  python query_tfda.py --qsd "醫兆"
  python query_tfda.py --leaflet "衛部醫器輸字第000001號"
  python query_tfda.py --keyword "尿液分析"
  python query_tfda.py --update-cache
        """,
    )

    # 查詢參數
    query = parser.add_argument_group("查詢條件（可組合使用）")
    query.add_argument("--license", type=str, help="許可證字號")
    query.add_argument("--product", type=str, help="產品名稱（中英文）")
    query.add_argument("--company", type=str, help="申請商/藥商名稱")
    query.add_argument("--manufacturer", type=str, help="製造廠/廠牌名稱")
    query.add_argument("--reagent", type=str, help="試劑名稱/檢測項目")
    query.add_argument("--keyword", type=str, help="全文關鍵字搜尋")
    query.add_argument("--qsd", type=str, help="查詢 QSD/QMS 登錄")
    query.add_argument("--leaflet", type=str, help="查詢仿單/外盒")

    # 輸出控制
    output = parser.add_argument_group("輸出控制")
    output.add_argument("--json", action="store_true", help="輸出 JSON 格式")
    output.add_argument("--limit", type=int, default=0, help="限制顯示筆數（0=不限制）")
    output.add_argument("--group-by", type=str, choices=["manufacturer", "company_name"],
                        help="依指定欄位分組顯示")
    output.add_argument("--count-only", action="store_true",
                        help="只輸出筆數，不列出內容（快速預估）")

    # 快取管理
    cache = parser.add_argument_group("快取管理")
    cache.add_argument("--update-cache", action="store_true", help="更新本地快取")
    cache.add_argument("--cache-info", action="store_true", help="顯示快取狀態")

    # 執行與 log 行為
    misc = parser.add_argument_group("執行控制")
    misc.add_argument("--quiet", action="store_true",
                      help="抑制進度訊息，只輸出結果與錯誤")
    misc.add_argument("--verbose", action="store_true",
                      help="顯示 DEBUG 級詳細 log")
    misc.add_argument("--log-query", action="store_true",
                      help="將查詢字串記入 metrics.jsonl（預設不記，PII 考量）")
    misc.add_argument("--no-metrics", action="store_true",
                      help="停用 metrics 寫入（整段執行不追蹤）")

    return parser


def _cache_age_hours_for(query_type: str) -> Optional[float]:
    """取目前執行用到的資料集快取年齡（小時）。None 表示無快取資訊。"""
    from datetime import datetime as _dt
    mapping = {
        "company": "license", "manufacturer": "license", "reagent": "license",
        "product": "license", "keyword": "license", "license": "license",
        "qsd": "qsd", "leaflet": "leaflet",
    }
    key = mapping.get(query_type)
    if not key:
        return None
    info = get_cache_info().get(key, {})
    date_str = info.get("cache_date")
    if not date_str:
        return None
    try:
        d = _dt.strptime(date_str, "%Y-%m-%d")
        return (_dt.now() - d).total_seconds() / 3600.0
    except ValueError:
        return None


def main() -> None:
    """主程式入口。包一層 timing + metrics，實際邏輯在 _run_main。"""
    parser = build_parser()
    args = parser.parse_args()
    _configure_logging(quiet=args.quiet, verbose=args.verbose)

    start = time.perf_counter()
    state = {
        "query_type": "help",
        "result_count": 0,
        "fallback_used": [],
        "query": None,
    }
    try:
        _run_main(args, state, parser)
    finally:
        if not getattr(args, "no_metrics", False):
            duration_ms = (time.perf_counter() - start) * 1000.0
            record_metric(
                query_type=state["query_type"],
                result_count=state["result_count"],
                duration_ms=duration_ms,
                fallback_used=state["fallback_used"],
                cache_age_hours=_cache_age_hours_for(state["query_type"]),
                query=state["query"] if args.log_query else None,
            )


def _run_main(args, state: dict, parser: argparse.ArgumentParser) -> None:
    """實際執行查詢。state 為 mutable dict，供 main() 結尾寫 metrics。"""
    if args.log_query:
        # 只在使用者明確允許時才把查詢字串放進 state
        state["query"] = next(
            (getattr(args, f, None) for f in (
                "license", "company", "manufacturer", "reagent", "product",
                "keyword", "qsd", "leaflet",
            ) if getattr(args, f, None)),
            None,
        )

    # 快取管理
    if args.update_cache:
        state["query_type"] = "update_cache"
        log.info("正在更新所有資料集快取...")
        update_all_cache()
        log.info("快取更新完成。")
        return

    if args.cache_info:
        state["query_type"] = "cache_info"
        info = get_cache_info()
        print("快取狀態：")
        for key, val in info.items():
            status = "✅ 有效" if val["valid"] else ("⚠️ 過期" if val["cached"] else "❌ 無快取")
            date = val["cache_date"] or "N/A"
            print(f"  {val['name']}：{status}（{date}）")
        return

    # 檢查是否有查詢條件
    has_query = any([
        args.license, args.product, args.company, args.manufacturer,
        args.reagent, args.keyword, args.qsd, args.leaflet,
    ])

    if not has_query:
        parser.print_help()
        return

    # === QSD 查詢 ===
    if args.qsd:
        state["query_type"] = "qsd"
        log.info("正在查詢 QSD/QMS 資料：%s ...", args.qsd)
        try:
            qsd_data = load_dataset("qsd")
            qsd_normalized = normalize_dataset(qsd_data, "qsd")
            results = search_qsd(qsd_normalized, args.qsd)
            state["result_count"] = len(results)

            if args.count_only:
                print(f"共找到 {len(results)} 筆")
                return
            if args.json:
                print(format_json(results))
            else:
                print(format_qsd_table(results))
                print(format_cache_footer(get_cache_info()))
        except Exception as e:
            log.error("錯誤：%s", e)
        return

    # === 仿單查詢 ===
    if args.leaflet:
        state["query_type"] = "leaflet"
        log.info("正在查詢仿單/外盒：%s ...", args.leaflet)
        try:
            leaflet_data = load_dataset("leaflet")
            leaflet_normalized = normalize_dataset(leaflet_data, "leaflet")
            results = search_leaflet(leaflet_normalized, args.leaflet)
            state["result_count"] = len(results)

            if args.count_only:
                print(f"共找到 {len(results)} 筆")
                return
            if args.json:
                print(format_json(results))
            else:
                print(format_leaflet_table(results))
                print(format_cache_footer(get_cache_info()))
        except Exception as e:
            log.error("錯誤：%s", e)
        return

    # === 許可證查詢（主資料集） ===
    log.info("正在載入許可證資料集...")
    try:
        license_data = load_dataset("license")
        license_normalized = normalize_dataset(license_data, "license")
    except Exception as e:
        log.error("無法載入許可證資料集 — %s", e)
        sys.exit(1)

    results = None

    # === license 為 exclusive 查詢：找到後附仿單連結後直接結束路由 ===
    if args.license:
        state["query_type"] = "license"
        log.info("查詢許可證字號：%s", args.license)
        results = search_by_license_no(license_normalized, args.license)

        if results:
            try:
                leaflet_data = load_dataset("leaflet")
                leaflet_normalized = normalize_dataset(leaflet_data, "leaflet")
                for row, mt in results:
                    ln = get_field(row, "license_no")
                    leaflet_hits = search_leaflet(leaflet_normalized, ln)
                    if leaflet_hits:
                        lr = leaflet_hits[0][0]
                        row["_leaflet_url"] = get_field(lr, "leaflet_url")
                        row["_package_url"] = get_field(lr, "package_url")
            except Exception as e:
                log.debug("仿單連結查詢失敗（非致命）：%s", e)

    else:
        # === 組合查詢：用決策表決定 primary + cross filters ===
        primary, cross_filters = plan_query(args)

        if primary is None:
            log.warning("未指定有效的查詢條件。")
            return

        state["query_type"] = primary
        primary_value = getattr(args, primary)
        if cross_filters:
            parts = [f"{_field_label_zh(primary)}={primary_value}"] + [
                f"{_field_label_zh(k)}={v}" for k, v in cross_filters.items()
            ]
            log.info("組合查詢：%s", ", ".join(parts))
        else:
            log.info("查詢%s：%s", _field_label_zh(primary), primary_value)

        alias_used = None
        if primary in _ALIAS_AWARE_SEARCH:
            results, alias_used = _ALIAS_AWARE_SEARCH[primary](
                license_normalized, primary_value
            )
        else:
            results = _PRIMARY_SEARCH[primary](license_normalized, primary_value)

        if alias_used:
            state["fallback_used"].append("alias")
            log.info("提示：原查詢「%s」0 筆，透過 alias「%s」查到結果",
                     primary_value, alias_used)

        # 0 筆 + 有 distinct 欄位可查 → 提供「是不是要查 XXX」建議
        if not results and primary in _SUGGEST_FIELD_MAP:
            distinct = distinct_field_values(
                license_normalized, _SUGGEST_FIELD_MAP[primary]
            )
            suggestions = suggest_similar(primary_value, distinct, n=3, cutoff=0.5)
            if suggestions:
                state["fallback_used"].append("suggest")
                log.warning("查無「%s」相關資料，是不是要查：", primary_value)
                for s in suggestions:
                    log.warning("  - %s", s)

        if cross_filters:
            results = apply_cross_filter(results, **cross_filters)

    state["result_count"] = len(results) if results else 0

    # === 輸出 ===
    if args.count_only:
        print(f"共找到 {len(results)} 筆")
        return
    if args.json:
        print(format_json(results))
        return

    # 超過 30 筆先顯示摘要（對齊 SKILL.md 檢查點）
    if len(results) > 30 and not args.limit:
        group_field = args.group_by or "manufacturer"
        print(format_summary(results, group_field))
        print()

    # 決定顯示格式
    use_grouping = (
        args.group_by == "manufacturer"
        or (args.company and not args.group_by)
        or (args.manufacturer and args.company)
    )

    limit = args.limit if args.limit > 0 else 0

    if use_grouping:
        print(format_grouped_by_manufacturer(results, limit=limit))
    else:
        display_limit = args.limit if args.limit > 0 else (10 if len(results) > 30 else len(results))
        print(format_license_table(results, limit=display_limit))

    # 仿單連結（若有）
    has_leaflet = any(r.get("_leaflet_url") for r, _ in results)
    if has_leaflet:
        print("\n### 仿單連結")
        for row, _ in results:
            lf = row.get("_leaflet_url", "")
            pk = row.get("_package_url", "")
            if lf and lf != "N/A":
                ln = get_field(row, "license_no")
                print(f"- {ln} 說明書：{lf}")
            if pk and pk != "N/A":
                ln = get_field(row, "license_no")
                print(f"- {ln} 外盒：{pk}")

    print(format_cache_footer(get_cache_info()))


if __name__ == "__main__":
    main()
