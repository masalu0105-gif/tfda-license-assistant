# TFDA License Assistant

Claude Code 自訂 skill：查詢台灣衛福部食品藥物管理署（TFDA）開放資料中的醫療器材許可證、QSD 登錄、仿單 / 外盒連結。核心查詢以純 Python 標準函式庫實作，資料來自 `data.fda.gov.tw`，24 小時快取。

## 安裝

```bash
git clone https://github.com/masalu0105-gif/tfda-license-assistant.git
cd tfda-license-assistant

# 核心查詢（無額外依賴）
# scripts/ 僅用 Python 3.8+ 標準函式庫，不需 pip install

# 首次使用先抓資料（~20 秒）
python scripts/query_tfda.py --update-cache
```

### 安裝為 Claude Code skill

```bash
mkdir -p ~/.claude/skills/
ln -s "$(pwd)" ~/.claude/skills/tfda-license-assistant
```

之後在 Claude Code 問「查 ARKRAY 在台灣有哪些醫療器材」或「醫兆代理的 HbA1c 試劑」即會自動觸發。詳見 `SKILL.md` 的觸發詞與互動檢查點。

## 常用查詢

```bash
# 1. 查某公司名下所有醫療器材（依製造廠分組）
python scripts/query_tfda.py --company "醫兆"

# 2. 查某廠牌在台灣的代理商與產品
python scripts/query_tfda.py --manufacturer "ARKRAY"

# 3. 查試劑 / 檢測項目（多欄位搜尋）
python scripts/query_tfda.py --reagent "HbA1c"

# 4. 組合查詢（公司 × 廠牌 × 試劑 AND）
python scripts/query_tfda.py --company "醫兆" --manufacturer "ARKRAY"

# 5. 查單一許可證 + 仿單
python scripts/query_tfda.py --license "衛部醫器輸字第000001號"
```

完整範例見 `examples/sample_queries.md`，所有 flag 見 `python scripts/query_tfda.py --help`。

## Repo 結構

| 目錄 | 用途 | 開源狀態 |
|------|------|---------|
| `scripts/` | 核心查詢 CLI 與模組，純公開 TFDA 資料 | 可完整開源 |
| `company/` | 公司內部版（掃網路磁碟、產 Excel 追蹤表） | 內部用，開源時移除此資料夾 |
| `tests/` | pytest 測試 + 去敏 fixture + golden output | 隨主程式碼 |
| `docs/` | ROADMAP 與設計文件 | 隨主程式碼 |

## 開發

```bash
# 安裝開發依賴（測試 + lint）
pip install -r requirements-dev.txt

# 跑所有測試
pytest tests/ -v

# 帶覆蓋率
pytest tests/ --cov=scripts --cov-report=term-missing

# 偵測 TFDA 源端 schema drift（本地快取更新後執行）
TFDA_SCHEMA_TARGET=cache pytest tests/test_schema_drift.py
```

## 資料來源

| InfoId | 資料集 | 筆數 | 更新頻率 |
|--------|--------|------|----------|
| 68 | 醫療器材許可證 | ~145K | 每週 |
| 70 | 仿單 / 外盒圖檔 | ~43K | 每週 |
| 111 | QMS 製造許可 | ~10K | 每週 |
| 112 | QSD 認可登錄 | ~41K | 每週 |

下載 URL：`https://data.fda.gov.tw/data/opendata/export/{InfoId}/csv`

資料為 TFDA 開放資料，請遵循 [政府資料開放授權條款 1.0](https://data.gov.tw/license)。本工具僅為查詢介面，不儲存或修改原始資料內容。

## 優化進度

見 `docs/ROADMAP.md`（Phase 0 / 1 完成，Phase 2+ 進行中）。
