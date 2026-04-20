# TFDA License Assistant — 優化路線圖 v1

本文件為可執行的驗收標準清單。每項完成後於 checkbox 打勾，commit message 引用對應編號（例如 `fix(P0.1): ...`）。

## 共通驗收原則

- **零回歸**：既有查詢行為（`examples/sample_queries.md` 的 10 個範例 + `test-prompts.json` 的 3 個場景）跑過後輸出不得劣化。
- **可重跑**：每條 DoD 必須是可貼進 terminal 的指令，退出碼 0 = 通過。
- **文件同步**：改 CLI flag、檢查點、fallback 行為時，`SKILL.md` 與程式碼必須同 PR 更新。
- **Commit 粒度**：一個 DoD 一個 commit，commit message 寫明對應的驗收項編號。

---

## Phase 0 — Bug 修正（最高優先，無依賴）

### [x] P0.1 修 `query_tfda.py` 組合查詢邏輯

| 項目 | 內容 |
|------|------|
| **改動範圍** | `scripts/query_tfda.py:174-224` |
| **完成定義** | (a) 移除 `getattr(args, '_primary', None)` dead code；(b) 組合查詢分派改為單一決策表：`(company, manufacturer, reagent, product, keyword)` 5 維布林 → 明確的 primary field + cross filters；(c) `apply_cross_filter` 的 company 參數不再用 `not any(...)` 詭異判斷；(d) 每種 2-flag 與 3-flag 組合都有對應測試。 |
| **驗證指令** | `pytest tests/test_cli_dispatch.py -v`（新增檔案，測 32 種 flag 組合的 primary field 與 filters 是否正確）+ `python scripts/query_tfda.py --company 醫兆 --manufacturer ARKRAY --reagent HbA1c`（三重組合不 crash）。 |
| **不能破壞** | `--company 醫兆` 單條件查詢結果筆數與修改前一致（±0 筆）。 |

### [x] P0.2 修 QSD 到期警示（文件 vs 程式碼矛盾）

| 項目 | 內容 |
|------|------|
| **改動範圍** | `scripts/tfda_formatter.py:183-216` `_get_validity_status` |
| **完成定義** | (a) 警示閾值參數化為 `WARNING_THRESHOLD_DAYS`，預設 180（對齊 SKILL.md「6 個月」）；(b) 修掉「`is_valid_field="是"` 時先 return 跳過日期判斷」的邏輯 bug，改為：先算日期狀態，再用 `is_valid_field` 作 fallback；(c) 過期判斷要同時考慮兩者，任一為 False 即顯示 ❌。 |
| **驗證指令** | `pytest tests/test_validity_status.py -v`，覆蓋 8 個 case：`(過期/即將到期/有效) × (is_valid="是"/"否"/空)` + 日期格式異常。 |
| **不能破壞** | 既有「❌ 已過期」標示行為不變。 |

### [x] P0.3 補 `_looks_like_license_no` 變體

| 項目 | 內容 |
|------|------|
| **改動範圍** | `scripts/tfda_search.py:219-222` |
| **完成定義** | 關鍵字表擴充至：`衛署, 衛部, 衛授, 醫器, 輸, 製, 陸輸, 診, 壹, 登, 字第`。用固定 fixture 100 筆真實/偽造的許可證字號跑 true/false 分類，precision + recall ≥ 0.95。 |
| **驗證指令** | `pytest tests/test_license_no_detection.py -v` |

---

## Phase 1 — 測試基礎建設（護航後續所有改動）

### [x] P1.1 建立 pytest + fixture 骨架

| 項目 | 內容 |
|------|------|
| **改動範圍** | 新增 `tests/`、`tests/conftest.py`、`tests/fixtures/` |
| **完成定義** | (a) `tests/fixtures/license_sample.csv`（50 筆去敏真實資料，涵蓋醫兆/ARKRAY/Sysmex/有註銷/有空欄）；(b) 同樣建 `leaflet_sample.csv`、`qsd_sample.csv`；(c) `conftest.py` 提供 `normalized_license_rows` fixture（載入 → normalize 好的 list）；(d) fixture 裡**不得**有個資（統編需亂數化、地址需 mask）。 |
| **驗證指令** | `pytest tests/ --co -q`（collection 成功）+ 人工 review fixture 確認去敏 |
| **不能破壞** | 真實快取 `~/.cache/tfda/` 不得被測試讀寫（用 `monkeypatch` 隔離）。 |

### [x] P1.2 單元測試：normalize / search / formatter

| 模組 | 覆蓋率門檻 | 重點 |
|------|-----------|------|
| `tfda_normalize.py` | branch coverage ≥ 90% | 「許可編號」在 QSD/QMS 的分流、缺欄位、空值 |
| `tfda_search.py` | branch coverage ≥ 85% | exact > contains > fuzzy 排序、cross filter AND 邏輯、_looks_like_license_no |
| `tfda_formatter.py` | branch coverage ≥ 80% | validity status 所有分支、分組排序、空結果 |

**驗證指令**：`pytest tests/ --cov=scripts --cov-report=term-missing --cov-fail-under=85`

### [x] P1.3 CLI end-to-end 測試（golden output）

| 項目 | 內容 |
|------|------|
| **改動範圍** | `tests/test_cli_e2e.py` + `tests/golden/` |
| **完成定義** | 用 `subprocess` 跑 10 個 `examples/sample_queries.md` 範例，輸出比對 `tests/golden/*.md`；快取走 fixture 不走網路。diff 出現才算失敗。 |
| **驗證指令** | `pytest tests/test_cli_e2e.py -v` |
| **接受的 diff** | 匹配類型（「完全匹配」「部分匹配」）欄位可忽略（用 normalizer 濾掉）。 |

### [x] P1.4 資料 schema snapshot 測試（偵測 TFDA 源端漂移）

| 項目 | 內容 |
|------|------|
| **改動範圍** | `tests/test_schema_drift.py`、`tests/schema/{license,leaflet,qsd,qms}.json` |
| **完成定義** | (a) 記錄每個資料集的欄位清單 + 必要欄位（`許可證字號` 等）+ 最小筆數下限；(b) 測試會讀 `~/.cache/tfda/*.csv`（若存在）或 skip；(c) 偵測到新增/刪除欄位時 fail 並列出 diff。 |
| **驗證指令** | `pytest tests/test_schema_drift.py -v`（本地有快取才跑，CI 用 fixture 版） |

### [x] P1.5 `test-prompts.json` 升格為 smoke test

| 項目 | 內容 |
|------|------|
| **完成定義** | (a) 為每筆 prompt 加 `expected_cli_args`、`expected_contains`（關鍵字 list）、`expected_row_count_min`；(b) 寫 `tests/test_prompts_smoke.py` 把 prompt parse 成 CLI 呼叫，驗證輸出；(c) 筆數從 3 擴至 10，對齊 `sample_queries.md`。 |
| **驗證指令** | `pytest tests/test_prompts_smoke.py -v` |

---

## Phase 2 — Repo 衛生

### [x] P2.1 README.md

**DoD**：包含 (a) 一段 2 句話專案定位；(b) Install 指令；(c) 5 個最常用查詢範例；(d) `scripts/` vs `company/` 分工說明；(e) 如何安裝為 Claude Code skill；(f) 資料來源與授權聲明。

**驗證**：請**另一位**沒看過此 repo 的同事照 README 跑一次 `--company 醫兆`，不需看程式碼即可成功。

### [x] P2.2 requirements 分拆

| 檔案 | 內容 |
|------|------|
| `scripts/requirements.txt` | 空（或只列開發用：`pytest`, `pytest-cov`, `ruff`） |
| `company/requirements.txt` | `pandas>=2.0`, `openpyxl>=3.1` |
| 根目錄 `requirements-dev.txt` | 測試 + lint 工具 |

**DoD**：`pip install -r scripts/requirements.txt` 後能跑完整 CLI；`pip install -r company/requirements.txt` 後能跑 `build_license_db.py`。

### [x] P2.3 GitHub Actions CI

**DoD**：(a) 在 push/PR 跑 ruff + pytest + coverage；(b) Python 3.8 / 3.10 / 3.12 三版 matrix；(c) `company/` 排除在公開 CI log 外（或確認無敏感資訊）；(d) coverage 低於 85% CI fail。

**驗證**：PR 建立後 Actions 顯示綠色；故意引入 syntax error 確認會紅。

### [x] P2.4 SKILL.md ↔ code 一致性檢查（防止未來分裂）

| 項目 | 內容 |
|------|------|
| **完成定義** | `tests/test_skill_md_consistency.py`：(a) parse SKILL.md「如何執行」區塊的所有 `--flag`，驗證 argparse 都有定義；(b) 反向檢查：argparse 的 flag 都要在 SKILL.md 出現；(c) 檢查點表格裡提到的行為（如 `--limit 5` 預覽）對應的 flag 存在。 |
| **驗證指令** | `pytest tests/test_skill_md_consistency.py -v` |

### [x] P2.5 硬編碼路徑修正

**DoD**：`SKILL.md` 範例路徑改為相對路徑或 `$SKILL_DIR`；`company/build_license_db.py` 的 `DEFAULT_BASE` 加環境變數 override（`TFDA_SCAN_BASE`）。

---

## Phase 3 — Fallback 實作（SKILL.md 承諾）

### [x] P3.1 全形 ↔ 半形正規化

| 項目 | 內容 |
|------|------|
| **完成定義** | `tfda_normalize.py` 新增 `to_halfwidth()`；0 筆時**自動**重試（不另外 fallback）——查詢字串與資料欄位**雙邊**都正規化為半形後比對，一次搞定不放大結果。 |
| **驗證** | `pytest tests/test_width_normalize.py`：「ＡＲＫＲＡＹ」查到 ARKRAY 的結果。 |
| **不能破壞** | 原本 ARKRAY → ARKRAY 的筆數 ±0。 |

### [x] P3.2 中英文廠牌 alias（外部 JSON）

| 項目 | 內容 |
|------|------|
| **改動範圍** | 新增 `scripts/aliases.json`（純 stdlib，**不引入 pyyaml 依賴**） |
| **完成定義** | (a) 初始 alias 表 ≤ 20 筆（ARKRAY/愛科萊、Sysmex/希森美康、Roche/羅氏、Abbott/亞培…）；(b) 查無結果時用 alias 重試一次，**在結果附上「透過 alias 查到」標記**；(c) 外部檔案改動不需改 code；(d) alias 檔案有 schema（key/values/source/updated_at）。 |
| **驗證** | `pytest tests/test_alias_fallback.py`：查「愛科萊」應查到 ARKRAY 結果。 |
| **維護流程** | PR 加 alias 必須附上來源（官方網站/TFDA 登錄紀錄截圖）。 |

### [x] P3.3 0 筆時「是不是要查 XXX」建議

| 項目 | 內容 |
|------|------|
| **效能限制** | 不得跑全表 `difflib`。預先建立 distinct values index（Phase 5 的 pre-index 的子集）：company names unique set ≤ 5000 筆、manufacturer ≤ 2000 筆。 |
| **完成定義** | 0 筆時對 distinct set 跑 `difflib.get_close_matches(n=3, cutoff=0.6)`，列最多 3 個建議。 |
| **驗證** | `pytest tests/test_typo_suggestion.py`：輸入「醫趙」應建議「醫兆」。 |
| **時間預算** | 建議計算 ≤ 200ms（單次 CLI 整體 ≤ 2s）。 |

### [x] P3.4 `--count-only` / 筆數 preview

**DoD**：(a) 新增 `--count-only` flag，只輸出 `共 N 筆` 不載入完整資料；(b) 無 flag 時若結果 > 30 筆，先印摘要再印表格（與現行一致但修 truncate 邏輯）。

**驗證**：`python query_tfda.py --company 醫兆 --count-only` 回一行數字。

---

## Phase 4 — Observability

### [x] P4.1 logging 取代 print

**DoD**：(a) 全部 `print` 分類為 stdout（結果）/ stderr（進度/警告）/ logging（debug）；(b) `--quiet` 抑制進度、`--verbose` 開 DEBUG；(c) 結果輸出不受 logging level 影響（給 pipe 用）。

**驗證**：`python query_tfda.py --company 醫兆 --json --quiet 2>/dev/null | jq .` 必須能成功 parse。

### [x] P4.2 Metrics（先 log-based）

**DoD**：每次 CLI 執行結束追加一行 JSON 到 `~/.cache/tfda/metrics.jsonl`：

```json
{"ts":"...","query_type":"company","result_count":45,"fallback_used":["alias"],"cache_age_hours":2,"duration_ms":340}
```

便於事後分析 fallback 觸發率、慢查詢。PII（查詢字串本身）預設**不記**，用 `--log-query` 才記。

### [x] P4.3 資料 schema drift 告警

**DoD**：`--update-cache` 完成後自動比對 `tests/schema/*.json`，欄位變動時印 WARNING（不 fail）並寫 `~/.cache/tfda/schema_drift.log`。

---

## Phase 5 — 效能（先量再改）

### [x] P5.1 Benchmark baseline（**先做這個**）

**DoD**：`scripts/bench.py` 跑 10 個代表性查詢，輸出 p50/p95 延遲與記憶體峰值。無 baseline 不做 P5.2/5.3。

**驗收門檻**：有數據，無具體數字門檻。

### [x] P5.2 Pre-index（依 benchmark 決定）

**觸發條件**：若 P5.1 顯示 `--company` 平均 > 500ms 才做。

**DoD**：(a) 首次 normalize 後建立 `{company_name → [row_idx]}`、`{manufacturer → [row_idx]}` dict，存 JSON（**不用 pickle**）到 `~/.cache/tfda/indexes.json`；(b) 快取失效條件：原 CSV mtime 變動；(c) 查詢延遲下降 ≥ 50%。

### [x] P5.3 Normalized 快取（最後做）— 實作但預設關閉

**觸發條件**：P5.2 後若冷啟動仍 > 1s 才做。**用 JSON 或 parquet，禁用 pickle**（安全 + 版本相容）。

---

## 砍掉的項目（明確記錄）

- Web UI（原 5.3）：工作量大、不在 skill 核心價值。
- 週對週變動報表（原 5.2）：延到 v1.3 再評估，不列入本輪。

---

## 總驗收（整個計畫完成）

- [ ] `pytest tests/ --cov=scripts --cov-fail-under=85`
- [ ] `ruff check scripts/ company/ tests/`
- [ ] CI 在 Python 3.8 / 3.10 / 3.12 全綠
- [ ] `examples/sample_queries.md` 的 10 個範例手動跑一次，輸出合理
- [ ] SKILL.md 與程式碼行為差異 = 0（由 P2.4 自動驗證）
- [ ] 新手照 README 能在 10 分鐘內跑第一個查詢
