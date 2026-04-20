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
import os
import sys

# 確保可以 import 同目錄模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tfda_datasets import get_cache_info, load_dataset, update_all_cache
from tfda_formatter import (
    format_cache_footer,
    format_grouped_by_manufacturer,
    format_json,
    format_leaflet_table,
    format_license_table,
    format_qsd_table,
    format_summary,
)
from tfda_normalize import get_field, normalize_dataset
from tfda_search import (
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

    # 快取管理
    cache = parser.add_argument_group("快取管理")
    cache.add_argument("--update-cache", action="store_true", help="更新本地快取")
    cache.add_argument("--cache-info", action="store_true", help="顯示快取狀態")

    return parser


def main() -> None:
    """主程式入口。"""
    parser = build_parser()
    args = parser.parse_args()

    # 快取管理
    if args.update_cache:
        print("正在更新所有資料集快取...")
        update_all_cache()
        print("快取更新完成。")
        return

    if args.cache_info:
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
        print(f"正在查詢 QSD/QMS 資料：{args.qsd} ...")
        try:
            qsd_data = load_dataset("qsd")
            qsd_normalized = normalize_dataset(qsd_data, "qsd")
            results = search_qsd(qsd_normalized, args.qsd)

            if args.json:
                print(format_json(results))
            else:
                print(format_qsd_table(results))
                print(format_cache_footer(get_cache_info()))
        except Exception as e:
            print(f"錯誤：{e}", file=sys.stderr)
        return

    # === 仿單查詢 ===
    if args.leaflet:
        print(f"正在查詢仿單/外盒：{args.leaflet} ...")
        try:
            leaflet_data = load_dataset("leaflet")
            leaflet_normalized = normalize_dataset(leaflet_data, "leaflet")
            results = search_leaflet(leaflet_normalized, args.leaflet)

            if args.json:
                print(format_json(results))
            else:
                print(format_leaflet_table(results))
                print(format_cache_footer(get_cache_info()))
        except Exception as e:
            print(f"錯誤：{e}", file=sys.stderr)
        return

    # === 許可證查詢（主資料集） ===
    print("正在載入許可證資料集...")
    try:
        license_data = load_dataset("license")
        license_normalized = normalize_dataset(license_data, "license")
    except Exception as e:
        print(f"錯誤：無法載入許可證資料集 — {e}", file=sys.stderr)
        sys.exit(1)

    results = None

    # === license 為 exclusive 查詢：找到後附仿單連結後直接結束路由 ===
    if args.license:
        print(f"查詢許可證字號：{args.license}")
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
            except Exception:
                pass

    else:
        # === 組合查詢：用決策表決定 primary + cross filters ===
        primary, cross_filters = plan_query(args)

        if primary is None:
            print("未指定有效的查詢條件。")
            return

        primary_value = getattr(args, primary)
        if cross_filters:
            parts = [f"{_field_label_zh(primary)}={primary_value}"] + [
                f"{_field_label_zh(k)}={v}" for k, v in cross_filters.items()
            ]
            print(f"組合查詢：{', '.join(parts)}")
        else:
            print(f"查詢{_field_label_zh(primary)}：{primary_value}")

        alias_used = None
        if primary in _ALIAS_AWARE_SEARCH:
            results, alias_used = _ALIAS_AWARE_SEARCH[primary](
                license_normalized, primary_value
            )
        else:
            results = _PRIMARY_SEARCH[primary](license_normalized, primary_value)

        if alias_used:
            print(f"提示：原查詢「{primary_value}」0 筆，透過 alias「{alias_used}」查到結果")

        # 0 筆 + 有 distinct 欄位可查 → 提供「是不是要查 XXX」建議
        if not results and primary in _SUGGEST_FIELD_MAP:
            distinct = distinct_field_values(
                license_normalized, _SUGGEST_FIELD_MAP[primary]
            )
            suggestions = suggest_similar(primary_value, distinct, n=3, cutoff=0.6)
            if suggestions:
                print(f"\n查無「{primary_value}」相關資料，是不是要查：")
                for s in suggestions:
                    print(f"  - {s}")

        if cross_filters:
            results = apply_cross_filter(results, **cross_filters)

    # === 輸出 ===
    if args.json:
        print(format_json(results))
        return

    # 超過 20 筆先顯示摘要
    if len(results) > 20 and not args.limit:
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
        display_limit = args.limit if args.limit > 0 else (10 if len(results) > 20 else len(results))
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
