"""TFDA 輸出格式化模組。

支援 markdown 表格、JSON 輸出、分組統計。
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from tfda_normalize import get_field


def format_license_table(results: List[Tuple[Dict, str]], limit: int = 10) -> str:
    """格式化許可證查詢結果為 markdown 表格。"""
    if not results:
        return "未找到符合條件的資料。"

    lines = []
    lines.append(f"共找到 **{len(results)}** 筆結果")
    lines.append("")

    display = results[:limit]

    lines.append("| 許可證字號 | 中文品名 | 申請商 | 製造廠 | 有效日期 | 匹配 |")
    lines.append("|---|---|---|---|---|---|")

    for row, match_type in display:
        license_no = get_field(row, "license_no")
        name_zh = get_field(row, "product_name_zh")
        company = get_field(row, "company_name")
        mfg = get_field(row, "manufacturer")
        valid = get_field(row, "valid_date")
        lines.append(f"| {license_no} | {name_zh} | {company} | {mfg} | {valid} | {match_type} |")

    if len(results) > limit:
        lines.append(f"\n（僅顯示前 {limit} 筆，共 {len(results)} 筆。可用 `--limit` 調整）")

    return "\n".join(lines)


def format_grouped_by_manufacturer(results: List[Tuple[Dict, str]], limit: int = 0) -> str:
    """依製造廠分組顯示結果。"""
    if not results:
        return "未找到符合條件的資料。"

    groups: Dict[str, List[Tuple[Dict, str]]] = defaultdict(list)
    for row, match_type in results:
        mfg = get_field(row, "manufacturer", "未知製造廠")
        groups[mfg].append((row, match_type))

    # 依數量排序
    sorted_groups = sorted(groups.items(), key=lambda x: -len(x[1]))

    lines = []
    lines.append(f"共找到 **{len(results)}** 筆結果，來自 **{len(groups)}** 個製造廠")
    lines.append("")

    # 摘要統計
    lines.append("### 製造廠分布")
    for mfg, items in sorted_groups:
        lines.append(f"- **{mfg}**：{len(items)} 筆")
    lines.append("")

    # 各組明細
    count = 0
    for mfg, items in sorted_groups:
        lines.append(f"### {mfg}（{len(items)} 筆）")
        lines.append("")
        lines.append("| 許可證字號 | 中文品名 | 英文品名 | 有效日期 |")
        lines.append("|---|---|---|---|")

        for row, match_type in items:
            if limit > 0 and count >= limit:
                remaining = len(results) - count
                lines.append(f"\n（已達顯示上限 {limit} 筆，尚有 {remaining} 筆未顯示）")
                return "\n".join(lines)

            license_no = get_field(row, "license_no")
            name_zh = get_field(row, "product_name_zh")
            name_en = get_field(row, "product_name_en")
            valid = get_field(row, "valid_date")
            lines.append(f"| {license_no} | {name_zh} | {name_en} | {valid} |")
            count += 1

        lines.append("")

    return "\n".join(lines)


def format_leaflet_table(results: List[Tuple[Dict, str]]) -> str:
    """格式化仿單/外盒查詢結果。"""
    if not results:
        return "未找到仿單/外盒資料。"

    lines = []
    lines.append(f"共找到 **{len(results)}** 筆仿單/外盒資料")
    lines.append("")
    lines.append("| 許可證字號 | 中文品名 | 說明書連結 | 包裝連結 |")
    lines.append("|---|---|---|---|")

    for row, match_type in results:
        license_no = get_field(row, "license_no")
        name_zh = get_field(row, "product_name_zh")
        leaflet = get_field(row, "leaflet_url")
        package = get_field(row, "package_url")

        leaflet_link = f"[查看]({leaflet})" if leaflet and leaflet != "N/A" else "N/A"
        package_link = f"[查看]({package})" if package and package != "N/A" else "N/A"

        lines.append(f"| {license_no} | {name_zh} | {leaflet_link} | {package_link} |")

    return "\n".join(lines)


def format_qsd_table(results: List[Tuple[Dict, str]]) -> str:
    """格式化 QSD 查詢結果，含到期警示。"""
    if not results:
        return "未找到 QSD/QMS 資料。"

    lines = []
    lines.append(f"共找到 **{len(results)}** 筆 QSD/QMS 資料")
    lines.append("")
    lines.append("| 許可編號 | 製造廠 | 藥商 | 有效期限 | 狀態 |")
    lines.append("|---|---|---|---|---|")

    for row, match_type in results:
        qsd_no = get_field(row, "qsd_no") or get_field(row, "qms_license_no")
        mfg = get_field(row, "manufacturer")
        company = get_field(row, "company_name")
        valid_date_str = get_field(row, "valid_date")
        is_valid = row.get("是否在3年有效期間內", "")

        status = _get_validity_status(valid_date_str, is_valid)
        lines.append(f"| {qsd_no} | {mfg} | {company} | {valid_date_str} | {status} |")

    return "\n".join(lines)


def format_json(results: List[Tuple[Dict, str]]) -> str:
    """輸出 JSON 格式。"""
    output = []
    for row, match_type in results:
        entry = dict(row)
        entry["_match_type"] = match_type
        output.append(entry)
    return json.dumps(output, ensure_ascii=False, indent=2)


def format_summary(results: List[Tuple[Dict, str]], group_field: str = "manufacturer") -> str:
    """輸出摘要統計。"""
    if not results:
        return "無資料。"

    groups: Dict[str, int] = defaultdict(int)
    for row, _ in results:
        key = get_field(row, group_field, "其他")
        groups[key] += 1

    sorted_groups = sorted(groups.items(), key=lambda x: -x[1])

    lines = [f"共 {len(results)} 筆，依{_field_label(group_field)}分組："]
    for name, count in sorted_groups[:10]:
        lines.append(f"  {name}：{count} 筆")
    if len(sorted_groups) > 10:
        others = sum(c for _, c in sorted_groups[10:])
        lines.append(f"  其他 {len(sorted_groups) - 10} 個：{others} 筆")

    return "\n".join(lines)


def format_cache_footer(cache_info: Dict[str, dict]) -> str:
    """產生快取狀態資訊。"""
    parts = []
    for key, info in cache_info.items():
        if info["cached"]:
            parts.append(f"{info['name']}（{info['cache_date']}）")
    if parts:
        return f"\n---\n資料來源：TFDA 開放資料（{', '.join(parts)}）"
    return "\n---\n資料來源：TFDA 開放資料"


def _get_validity_status(date_str: str, is_valid_field: str = "") -> str:
    """判斷有效期限狀態。"""
    if is_valid_field:
        if "否" in is_valid_field:
            return "❌ 已過期"
        if "是" in is_valid_field:
            # 進一步檢查是否即將到期
            pass

    if not date_str or date_str == "N/A":
        return "N/A"

    try:
        # 嘗試解析日期（常見格式）
        for fmt in ["%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"]:
            try:
                valid_date = datetime.strptime(date_str.strip(), fmt)
                now = datetime.now()
                if valid_date < now:
                    return "❌ 已過期"
                elif valid_date - now < timedelta(days=90):
                    return "⚠️ 即將到期"
                else:
                    return "✅ 有效"
            except ValueError:
                continue
    except Exception:
        pass

    # 用原始欄位判斷
    if is_valid_field and "是" in is_valid_field:
        return "✅ 有效"

    return "N/A"


def _field_label(field: str) -> str:
    """欄位名的中文標籤。"""
    labels = {
        "manufacturer": "製造廠",
        "company_name": "申請商",
        "device_class": "醫器級數",
        "manufacturer_country": "國別",
    }
    return labels.get(field, field)
