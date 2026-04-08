# Changelog

## [1.1.0] - 2026-04-08

### 新增
- `company/build_license_db.py`：公司版許可證追蹤表產生器
  - 遞迴掃描雲端資料庫所有品牌 PDF 及 Excel
  - 自動識別他廠授權（太暘/欣郁）
  - 輸出含不展延清單、未比對清單的多頁 Excel
  - `sys.path` 改為相對路徑，安裝後直接可用

### 結構調整
- `company/` — 公司內部版本，開源時移除此資料夾即可
- `scripts/` — 核心查詢功能，純公開 TFDA 資料，可完整開源
- `output/` — 已列入 .gitignore，Excel 輸出不進 repo

---

## [1.0.0] - 2026-04-08

### 新增
- `scripts/query_tfda.py`：CLI 查詢入口（許可證/公司/製造廠/試劑/QSD/仿單）
- `scripts/tfda_datasets.py`：資料集下載與快取（InfoId 68/70/111/112）
- `scripts/tfda_normalize.py`：34 欄位 mapping 與正規化
- `scripts/tfda_search.py`：精確+模糊+交叉篩選查詢
- `scripts/tfda_formatter.py`：markdown/JSON/分組統計輸出
- `examples/sample_queries.md`：10 個業務日常查詢範例

### 資料來源
- TFDA 醫療器材許可證（InfoId=68，~14.5 萬筆）
- 仿單/外盒圖檔（InfoId=70，~4.3 萬筆）
- QMS 製造許可（InfoId=111）
- QSD 認可登錄（InfoId=112）
- 所有資料來自 data.fda.gov.tw，每週更新，24 小時快取
