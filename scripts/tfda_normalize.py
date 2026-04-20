"""TFDA 欄位正規化與別名 mapping 模組。

處理不同資料集欄位名稱不一致的問題，
將原始欄位名對應到統一的內部欄位名。
"""

from typing import Dict, List


def to_halfwidth(text: str) -> str:
    """將全形英數、標點、空白轉半形。中文字元不受影響。

    用於搜尋比對前的正規化：「ＡＲＫＲＡＹ」→「ARKRAY」。
    查詢字與資料欄位雙邊都套用，可一次解決全形半形差異，
    不必再做「0 筆時重試」之類的額外邏輯。
    """
    if not text:
        return text
    out = []
    for ch in text:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            out.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


# 統一欄位名 → 可能的原始欄位名（依實測結果建立）
FIELD_ALIASES: Dict[str, List[str]] = {
    # === 許可證資料集 (InfoId=68) ===
    "license_no": ["許可證字號", "證號", "license_number"],
    "revoke_status": ["註銷狀態"],
    "revoke_date": ["註銷日期"],
    "revoke_reason": ["註銷理由"],
    "valid_date": ["有效日期", "有效期限", "效期"],
    "issue_date": ["發證日期"],
    "license_type": ["許可證種類"],
    "old_license_no": ["舊證字號"],
    "device_class": ["醫療器材級數"],
    "customs_doc_no": ["通關簽審文件編號"],
    "product_name_zh": ["中文品名", "品名"],
    "product_name_en": ["英文品名"],
    "efficacy": ["效能"],
    "dosage_form": ["劑型"],
    "packaging": ["包裝"],
    "main_category_1": ["醫器主類別一"],
    "sub_category_1": ["醫器次類別一"],
    "main_category_2": ["醫器主類別二"],
    "sub_category_2": ["醫器次類別二"],
    "main_category_3": ["醫器主類別三"],
    "sub_category_3": ["醫器次類別三"],
    "ingredients": ["主成分略述"],
    "spec": ["醫器規格", "規格", "型號", "產品規格"],
    "restrictions": ["限制項目"],
    "company_name": ["申請商名稱", "藥商名稱", "公司名稱", "醫療器材商名稱"],
    "company_addr": ["申請商地址"],
    "company_tax_id": ["申請商統一編號"],
    "manufacturer": ["製造商名稱", "製造廠名稱", "製造商", "製造廠"],
    "manufacturer_addr": ["製造廠廠址", "製造廠地址"],
    "manufacturer_company_addr": ["製造廠公司地址"],
    "manufacturer_country": ["製造廠國別", "國別"],
    "process": ["製程"],
    "change_date": ["異動日期"],
    "mfg_license_no": ["製造許可登錄編號"],

    # === 仿單/外盒資料集 (InfoId=70) ===
    "leaflet_url": ["說明書圖檔連結", "仿單圖檔連結", "仿單連結"],
    "package_url": ["包裝圖檔連結", "外盒圖檔連結", "外盒連結"],

    # === QMS 資料集 (InfoId=111) ===
    "qms_license_no": ["許可編號"],
    "qms_scope": ["許可項目及作業內容"],
    "qms_valid": ["是否在3年有效期間內"],

    # === QSD 資料集 (InfoId=112) ===
    "qsd_no": ["許可編號", "QSD號碼", "登錄號碼", "QSD_number"],
    "qsd_scope": ["許可項目及作業內容"],
    "qsd_valid": ["是否在3年有效期間內"],
}

# 反向索引：原始欄位名 → 統一欄位名
_REVERSE_MAP: Dict[str, str] = {}
for unified, aliases in FIELD_ALIASES.items():
    for alias in aliases:
        _REVERSE_MAP[alias] = unified


def normalize_row(row: Dict[str, str], dataset_key: str = "") -> Dict[str, str]:
    """將一筆資料的欄位名正規化為統一名稱。

    保留原始欄位名，同時新增統一欄位名的 key。
    若原始欄位名已在 mapping 中，新增對應的統一名稱。
    """
    normalized = {}
    for key, value in row.items():
        key_stripped = key.strip()
        # 保留原始欄位
        normalized[key_stripped] = value
        # 加入統一名稱
        if key_stripped in _REVERSE_MAP:
            unified = _REVERSE_MAP[key_stripped]
            # QSD 和 QMS 的「許可編號」衝突處理
            if key_stripped == "許可編號":
                if dataset_key == "qsd":
                    normalized["qsd_no"] = value
                elif dataset_key == "qms":
                    normalized["qms_license_no"] = value
                else:
                    normalized[unified] = value
            else:
                normalized[unified] = value

    return normalized


def normalize_dataset(rows: List[Dict[str, str]], dataset_key: str = "") -> List[Dict[str, str]]:
    """正規化整個資料集的欄位名。"""
    return [normalize_row(row, dataset_key) for row in rows]


def get_field(row: Dict[str, str], unified_name: str, default: str = "N/A") -> str:
    """從一筆資料中取得統一欄位值。

    先查統一名稱，再查所有可能的原始欄位名。
    """
    if unified_name in row and row[unified_name]:
        return row[unified_name]

    aliases = FIELD_ALIASES.get(unified_name, [])
    for alias in aliases:
        if alias in row and row[alias]:
            return row[alias]

    return default


def get_searchable_text(row: Dict[str, str]) -> str:
    """組合一筆資料中所有文字欄位，用於全文搜尋。"""
    text_fields = [
        "product_name_zh", "product_name_en", "company_name",
        "manufacturer", "spec", "efficacy", "ingredients",
        "中文品名", "英文品名", "申請商名稱", "製造商名稱",
        "製造廠名稱", "醫器規格", "效能", "主成分略述",
    ]
    parts = []
    for field in text_fields:
        val = row.get(field, "")
        if val and val != "N/A":
            parts.append(val)
    return " ".join(parts)
