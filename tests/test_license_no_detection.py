"""P0.3 驗收測試：`_looks_like_license_no` 偵測準確度。

DoD：100 筆混合樣本跑 true/false 分類，precision + recall ≥ 0.95。

測試集設計：
- 50 筆真實許可證字號（含各種類別前綴與變體）
- 50 筆產品名稱 / 公司名 / 含誤導字元（輸入/製造/診斷等常見查詢）
"""

from tfda_search import _looks_like_license_no


# 50 筆 positive：真實許可證字號格式（含舊/新、多類別）
POSITIVE_CASES = [
    # 衛部醫器輸字
    "衛部醫器輸字第034001號",
    "衛部醫器輸字第000001號",
    "衛部醫器輸字第099999號",
    "衛部醫器輸字第041003號",
    "衛部醫器輸字第052001號",
    "衛部醫器輸字第060001號",
    "衛部醫器輸字第A12345號",
    "衛部醫器輸字第034004號",
    # 衛署醫器輸字（舊證）
    "衛署醫器輸字第019001號",
    "衛署醫器輸字第000123號",
    "衛署醫器輸字第025678號",
    "衛署醫器輸字第001234號",
    # 衛部醫器製字（國產）
    "衛部醫器製字第005001號",
    "衛部醫器製字第001234號",
    "衛部醫器製字第009876號",
    "衛部醫器製字第003456號",
    # 衛署醫器製字
    "衛署醫器製字第003456號",
    "衛署醫器製字第000789號",
    # 陸輸
    "衛部醫器陸輸字第000123號",
    "衛部醫器陸輸字第000456號",
    "衛部醫器陸輸字第000789號",
    # 輸壹（舊系列壹字）
    "衛部醫器輸壹字第000456號",
    "衛部醫器輸壹字第001234號",
    "衛部醫器輸壹字第000001號",
    # QSD 登字
    "QSD登字第000123號",
    "衛部醫器登字第012345號",
    # 診字（罕見但存在）
    "醫器診字第000001號",
    # 衛授（食品/化粧品有用，但偶爾跨類）
    "衛授食字第005678號",
    # 含前後文的自然查詢
    "查 衛部醫器輸字第034001號",
    "衛部醫器輸字第034001號 的仿單",
    "幫我找衛部醫器輸字第034001號",
    "許可證：衛部醫器輸字第034001號",
    # 空白變體
    "衛部 醫器 輸字 第034001號",
    "衛部醫器輸字第 034001 號",
    # 數字前綴變體（A 開頭）
    "衛部醫器輸字第A00123號",
    "衛部醫器製字第A09876號",
    # 多筆連貫（單一輸入）
    "衛部醫器輸字第034001號,衛部醫器輸字第034002號",
    # 其他正確前綴
    "衛部醫器輸字第000002號",
    "衛部醫器輸字第034002號",
    "衛部醫器輸字第034003號",
    "衛部醫器輸字第041001號",
    "衛部醫器輸字第041002號",
    "衛部醫器輸字第028501號",
    "衛部醫器輸字第028502號",
    "衛部醫器輸字第052002號",
    "衛部醫器輸字第052003號",
    "衛部醫器輸字第060002號",
    "衛部醫器陸輸字第000999號",
    "衛部醫器製字第000001號",
    "衛署醫器輸字第019999號",
    "衛部醫器輸壹字第099999號",
]

# 50 筆 negative：產品名、公司名、含易誤判字元的常見查詢
NEGATIVE_CASES = [
    # 產品名（中）
    "糖化血紅素分析試劑",
    "糖化血色素試劑",
    "血糖分析試劑",
    "尿液分析儀",
    "尿液分析試紙",
    "全自動血球計數儀",
    "白血球分類試劑",
    "全自動生化分析儀",
    "葡萄糖試劑",
    "血糖機",
    "血糖檢測試紙",
    "心臟節律器",
    "醫用口罩",
    "醫用酒精棉片",
    # 產品名（英）
    "HbA1c Reagent Kit",
    "Glucose Reagent",
    "Urine Analyzer",
    "Automated Hematology Analyzer",
    "Blood Glucose Test Strip",
    "Cardiac Pacemaker",
    # 公司名
    "醫兆科技股份有限公司",
    "亞培股份有限公司",
    "羅氏診斷產品股份有限公司",  # 含「診」
    "台灣衛材股份有限公司",       # 含「衛」(單字)
    "康泰生技股份有限公司",
    "大陸進口股份有限公司",        # 含「陸」(單字)
    # 廠牌
    "ARKRAY",
    "Sysmex",
    "Roche",
    "Abbott",
    "Bio-Rad",
    # 含易誤判字元的查詢
    "HbA1c 診斷試劑",              # 含「診」(單字)
    "體外診斷設備",                # 含「診」(單字)
    "診斷試劑代理商",              # 含「診」
    "製造商 ARKRAY",              # 含「製」(單字)
    "製造廠資訊",                  # 含「製」(單字)
    "輸入代理商",                  # 含「輸」(單字)
    "輸入商查詢",                  # 含「輸」(單字)
    "陸上運輸設備",                # 含「陸」「輸」(單字)
    "登山用品",                    # 含「登」(單字)
    "壹週刊報導",                  # 含「壹」(單字)
    # 自由描述
    "HbA1c 試劑在台灣有哪些",
    "尿液分析在哪幾家公司",
    "血糖機代理商",
    "查醫兆代理的 ARKRAY 產品",
    "幫我找 Sysmex 的血球試劑",
    "糖尿病檢測相關產品",
    "檢驗試劑清單",
    "生化分析設備",
    "免疫分析儀器",
    "血液分析試劑",
]


def test_positive_cases_detected():
    """真實許可證字號應 100% 偵測為 True（recall ≥ 95%）。"""
    misses = [s for s in POSITIVE_CASES if not _looks_like_license_no(s)]
    recall = (len(POSITIVE_CASES) - len(misses)) / len(POSITIVE_CASES)
    assert recall >= 0.95, f"Recall {recall:.2%} 未達 95%，漏判：{misses}"


def test_negative_cases_rejected():
    """產品/公司名應拒絕（FP 率 ≤ 5%）。"""
    false_positives = [s for s in NEGATIVE_CASES if _looks_like_license_no(s)]
    fp_rate = len(false_positives) / len(NEGATIVE_CASES)
    assert fp_rate <= 0.05, f"FP 率 {fp_rate:.2%} 超過 5%，誤判：{false_positives}"


def test_precision_recall_combined():
    """DoD 指標：precision + recall ≥ 0.95（單一指標）。"""
    tp = sum(1 for s in POSITIVE_CASES if _looks_like_license_no(s))
    fp = sum(1 for s in NEGATIVE_CASES if _looks_like_license_no(s))
    fn = len(POSITIVE_CASES) - tp
    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    assert precision >= 0.95, f"Precision {precision:.2%}"
    assert recall >= 0.95, f"Recall {recall:.2%}"


def test_total_sample_size():
    """確認樣本數 ≥ 100（DoD 規定）。"""
    assert len(POSITIVE_CASES) + len(NEGATIVE_CASES) >= 100


def test_regression_product_names_with_trap_chars():
    """回歸：含「輸/製/診/陸/登/壹」單字的查詢必須為 False（舊版 FP）。"""
    traps = [
        "輸入代理",
        "製造商",
        "體外診斷",
        "登山用品",
        "壹週刊",
    ]
    for q in traps:
        assert not _looks_like_license_no(q), f"誤判：{q!r}"


def test_empty_input():
    assert _looks_like_license_no("") is False
    assert _looks_like_license_no(None or "") is False
