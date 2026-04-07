# TFDA 查詢範例

## 代理商日常查詢場景

### 1. 查公司所有產品（依製造廠分組）
```bash
python scripts/query_tfda.py --company "醫兆"
```
**場景**：業務主管想看公司名下所有代理的產品，依廠牌分組了解產品線分布。

### 2. 查公司代理的特定廠牌產品（組合查詢）
```bash
python scripts/query_tfda.py --company "醫兆" --manufacturer "ARKRAY"
```
**場景**：業務想確認「我們代理的 ARKRAY 產品有哪些」。

### 3. 查試劑/檢測項目
```bash
python scripts/query_tfda.py --reagent "HbA1c"
python scripts/query_tfda.py --reagent "尿液分析"
python scripts/query_tfda.py --reagent "glucose"
python scripts/query_tfda.py --reagent "血球計數"
```
**場景**：客戶詢問「你們有沒有 HbA1c 的試劑」，業務需要快速查詢所有相關產品。

### 4. 查特定許可證（含仿單連結）
```bash
python scripts/query_tfda.py --license "衛部醫器輸字第000001號"
python scripts/query_tfda.py --leaflet "衛部醫器輸字第000001號"
```
**場景**：需要找某張許可證的詳細資訊和仿單 PDF。

### 5. 查 QSD 到期狀態
```bash
python scripts/query_tfda.py --qsd "醫兆"
```
**場景**：法規人員需要追蹤公司的 QSD 到期日，確保及時續約。

### 6. 查競品（某廠牌在台灣的代理商分布）
```bash
python scripts/query_tfda.py --manufacturer "Sysmex"
python scripts/query_tfda.py --manufacturer "Beckman Coulter"
```
**場景**：業務想了解競爭對手的產品線，看 Sysmex 在台灣有哪些代理商、哪些產品。

### 7. 組合查詢 — 特定廠牌的特定類型產品
```bash
python scripts/query_tfda.py --manufacturer "Sysmex" --reagent "CBC"
python scripts/query_tfda.py --company "醫兆" --reagent "HbA1c"
```
**場景**：交叉篩選，快速定位目標產品。

### 8. 全文關鍵字搜尋
```bash
python scripts/query_tfda.py --keyword "尿液分析"
python scripts/query_tfda.py --keyword "免疫分析"
```
**場景**：不確定該用哪個欄位查，先用關鍵字全文搜尋。

### 9. 輸出 JSON（串接其他工具）
```bash
python scripts/query_tfda.py --company "醫兆" --json
python scripts/query_tfda.py --reagent "HbA1c" --json > hba1c_results.json
```

### 10. 快取管理
```bash
# 檢查快取狀態
python scripts/query_tfda.py --cache-info

# 更新所有快取
python scripts/query_tfda.py --update-cache
```
