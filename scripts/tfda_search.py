"""TFDA 查詢函式模組。

提供精確匹配、包含比對、模糊比對，以及多欄位交叉篩選功能。
"""

import difflib
import re
from typing import Dict, List, Optional, Tuple

from tfda_normalize import get_field, get_searchable_text, to_halfwidth

# 許可證字號偵測：用 pattern 組合提高精準度，避免單一字（輸/製/診）誤判
# 涵蓋：衛[部署授]、醫器、輸字/製字/輸壹字/陸輸字/登字/診字、字第數字
_LICENSE_NO_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"衛[部署授]"),
    re.compile(r"醫器"),
    re.compile(r"[輸製][壹一二三]?字"),
    re.compile(r"陸輸"),
    re.compile(r"字第\s*[A-Za-z]?\d"),
    re.compile(r"[診登]字"),
)


# 可組合查詢的欄位（依優先順序當 primary）
COMBINABLE_FIELDS: Tuple[str, ...] = (
    "company", "manufacturer", "reagent", "product", "keyword",
)


def plan_query(args) -> Tuple[Optional[str], Dict[str, str]]:
    """決定組合查詢的 primary field 與 cross filters。

    輸入 argparse.Namespace（或任何 getattr 可讀的物件），
    回傳 (primary_field, cross_filters_dict)。

    - primary_field 依 COMBINABLE_FIELDS 順序取第一個有值的欄位。
    - cross_filters 包含所有「有值且非 primary」的欄位。
    - 若沒有任何 combinable 欄位有值，回傳 (None, {})。
    - 本函式為純函式，不做 I/O，便於單元測試。
    """
    provided = {
        field: getattr(args, field, None)
        for field in COMBINABLE_FIELDS
        if getattr(args, field, None)
    }
    if not provided:
        return None, {}
    primary = next((f for f in COMBINABLE_FIELDS if f in provided), None)
    cross_filters = {k: v for k, v in provided.items() if k != primary}
    return primary, cross_filters


# 匹配類型標記
MATCH_EXACT = "完全匹配"
MATCH_CONTAINS = "部分匹配"
MATCH_FUZZY = "模糊匹配"


def _match_value(query: str, value: str, fuzzy_cutoff: float = 0.5) -> Optional[str]:
    """比對單一值，回傳匹配類型或 None。

    查詢字與欄位值雙邊都做全形→半形 + 大小寫正規化，
    故「ＡＲＫＲＡＹ」vs「ARKRAY」可直接命中 exact。
    """
    if not value or not query:
        return None

    q = to_halfwidth(query).lower().strip()
    v = to_halfwidth(value).lower().strip()

    # 完全匹配
    if q == v:
        return MATCH_EXACT

    # 包含比對
    if q in v or v in q:
        return MATCH_CONTAINS

    # 模糊比對
    matches = difflib.get_close_matches(q, [v], n=1, cutoff=fuzzy_cutoff)
    if matches:
        return MATCH_FUZZY

    return None


def search_by_license_no(rows: List[Dict], license_no: str) -> List[Tuple[Dict, str]]:
    """依許可證字號查詢。"""
    results = []
    # 清理輸入，支援各種格式
    q = license_no.strip()

    for row in rows:
        val = get_field(row, "license_no", "")
        match_type = _match_value(q, val)
        if match_type:
            results.append((row, match_type))

    return _sort_results(results)


def search_by_company(rows: List[Dict], company_name: str) -> List[Tuple[Dict, str]]:
    """依申請商/藥商名稱查詢。"""
    results = []
    q = company_name.strip()

    for row in rows:
        val = get_field(row, "company_name", "")
        match_type = _match_value(q, val)
        if match_type:
            results.append((row, match_type))

    return _sort_results(results)


def search_by_manufacturer(rows: List[Dict], manufacturer: str) -> List[Tuple[Dict, str]]:
    """依製造廠/廠牌名稱查詢（放寬模糊比對 cutoff）。"""
    results = []
    q = manufacturer.strip()

    for row in rows:
        val = get_field(row, "manufacturer", "")
        match_type = _match_value(q, val, fuzzy_cutoff=0.4)
        if match_type:
            results.append((row, match_type))

    return _sort_results(results)


def search_by_product(rows: List[Dict], product_name: str) -> List[Tuple[Dict, str]]:
    """依產品名稱（中英文）查詢。"""
    results = []
    q = product_name.strip()

    for row in rows:
        zh = get_field(row, "product_name_zh", "")
        en = get_field(row, "product_name_en", "")

        match_zh = _match_value(q, zh)
        match_en = _match_value(q, en)

        # 取最佳匹配
        best = _best_match(match_zh, match_en)
        if best:
            results.append((row, best))

    return _sort_results(results)


def search_by_reagent(rows: List[Dict], reagent: str) -> List[Tuple[Dict, str]]:
    """依試劑名稱/檢測項目搜尋（多欄位）。"""
    results = []
    q = reagent.strip()

    search_fields = [
        "product_name_zh", "product_name_en", "spec",
        "中文品名", "英文品名", "醫器規格", "效能",
    ]

    for row in rows:
        best_match = None
        for field in search_fields:
            val = row.get(field, "") or get_field(row, field, "")
            if not val or val == "N/A":
                continue
            match_type = _match_value(q, val)
            best_match = _best_match(best_match, match_type)

        if best_match:
            results.append((row, best_match))

    return _sort_results(results)


def search_by_keyword(rows: List[Dict], keyword: str) -> List[Tuple[Dict, str]]:
    """全文關鍵字搜尋（搜尋所有文字欄位）。"""
    results = []
    q = keyword.strip().lower()

    for row in rows:
        text = get_searchable_text(row).lower()
        if q in text:
            results.append((row, MATCH_CONTAINS))

    return results


def search_qsd(rows: List[Dict], query: str) -> List[Tuple[Dict, str]]:
    """查詢 QSD 資料（支援公司名稱或製造廠名稱）。"""
    results = []
    q = query.strip()

    for row in rows:
        company = get_field(row, "company_name", "")
        manufacturer = get_field(row, "manufacturer", "")

        match_company = _match_value(q, company)
        match_mfg = _match_value(q, manufacturer)

        best = _best_match(match_company, match_mfg)
        if best:
            results.append((row, best))

    return _sort_results(results)


def search_leaflet(rows: List[Dict], query: str) -> List[Tuple[Dict, str]]:
    """查詢仿單/外盒（支援許可證字號或產品名稱）。"""
    results = []
    q = query.strip()

    is_license = _looks_like_license_no(q)

    for row in rows:
        if is_license:
            val = get_field(row, "license_no", "")
            match_type = _match_value(q, val)
        else:
            zh = get_field(row, "product_name_zh", "")
            en = get_field(row, "product_name_en", "")
            match_type = _best_match(_match_value(q, zh), _match_value(q, en))

        if match_type:
            results.append((row, match_type))

    return _sort_results(results)


def apply_cross_filter(
    results: List[Tuple[Dict, str]],
    company: Optional[str] = None,
    manufacturer: Optional[str] = None,
    reagent: Optional[str] = None,
    product: Optional[str] = None,
    keyword: Optional[str] = None,
) -> List[Tuple[Dict, str]]:
    """對已有結果套用交叉篩選條件（AND 邏輯）。"""
    filtered = results

    if company:
        filtered = [
            (row, mt) for row, mt in filtered
            if _match_value(company, get_field(row, "company_name", ""))
        ]

    if manufacturer:
        filtered = [
            (row, mt) for row, mt in filtered
            if _match_value(manufacturer, get_field(row, "manufacturer", ""), fuzzy_cutoff=0.4)
        ]

    if reagent:
        search_fields = ["product_name_zh", "product_name_en", "spec", "中文品名", "英文品名", "醫器規格"]
        filtered = [
            (row, mt) for row, mt in filtered
            if any(
                _match_value(reagent, row.get(f, "") or get_field(row, f, ""))
                for f in search_fields
            )
        ]

    if product:
        filtered = [
            (row, mt) for row, mt in filtered
            if _match_value(product, get_field(row, "product_name_zh", ""))
            or _match_value(product, get_field(row, "product_name_en", ""))
        ]

    if keyword:
        q = keyword.strip().lower()
        filtered = [
            (row, mt) for row, mt in filtered
            if q in get_searchable_text(row).lower()
        ]

    return filtered


def _looks_like_license_no(text: str) -> bool:
    """判斷輸入是否看起來像許可證字號。

    用多 pattern OR 判斷，只要命中任一條即視為許可證字號。
    pattern 組合取代舊版單字關鍵字（輸/製/診 單字會誤判「製造」
    「輸入」「診斷」等常見查詢）。
    """
    if not text:
        return False
    return any(p.search(text) for p in _LICENSE_NO_PATTERNS)


def _best_match(*match_types: Optional[str]) -> Optional[str]:
    """從多個匹配類型中取最佳。"""
    priority = {MATCH_EXACT: 3, MATCH_CONTAINS: 2, MATCH_FUZZY: 1}
    best = None
    best_score = 0
    for mt in match_types:
        if mt and priority.get(mt, 0) > best_score:
            best = mt
            best_score = priority[mt]
    return best


def _sort_results(results: List[Tuple[Dict, str]]) -> List[Tuple[Dict, str]]:
    """依匹配品質排序（完全 > 部分 > 模糊）。"""
    priority = {MATCH_EXACT: 0, MATCH_CONTAINS: 1, MATCH_FUZZY: 2}
    return sorted(results, key=lambda x: priority.get(x[1], 3))
