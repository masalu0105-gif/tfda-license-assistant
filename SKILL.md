---
name: tfda-license-assistant
description: |
  ALWAYS invoke this skill when the user asks anything about Taiwan TFDA medical device data — 查衛部/衛署許可證、查醫材許可證、查 TFDA、查 QSD/QMS 登錄、查仿單/外盒/package insert/IFU、查某公司/廠牌/製造廠代理產品、查某試劑或檢測項目的許可證、競品分析、代理商代理關係查詢。Do NOT answer from general knowledge; always run query_tfda.py for authoritative data.
  Triggers: 查許可證、查衛部、查衛署、查 TFDA、查醫材、查 QSD、查 QMS、查仿單、查外盒、查代理、查競品、醫療器材查詢、ARKRAY、Sysmex、Roche、Abbott、HbA1c、glucose、尿液分析、血糖機、試劑、醫兆、KB Medical.
  Use when: 業務競品分析、代理商查詢、客戶產品確認、QSD 到期追蹤、仿單下載需求。支援公司/許可證字號/製造廠/廠牌/試劑/檢測項目/關鍵字等條件查詢與組合查詢。
---

# TFDA 醫療器材查詢助手

## 何時啟用

當使用者提到以下任何情境時，啟用此 Skill：

- 查衛署許可證、查衛部許可證、查 TFDA 醫療器材、查醫材許可證
- 查某公司有哪些醫療器材產品（如「醫兆有哪些產品」）
- 查某廠牌/製造廠在台灣有哪些產品（如「ARKRAY 在台灣有哪些許可證」）
- 查某個試劑、檢測項目的許可證（如「HbA1c 試劑的許可證」）
- 查某公司代理的某廠牌產品（如「醫兆代理的 ARKRAY 有哪些」）
- 查 QSD、查 QMS 登錄、查 QSD 到期日
- 查仿單、查外盒、查 package insert、查 IFU
- 查醫療器材仿單連結
- 查某廠牌的競品、查誰在代理某個品牌

## 資料來源

| InfoId | 資料集 | 筆數 | 更新頻率 |
|--------|--------|------|----------|
| 68 | 醫療器材許可證 | ~145K | 每週 |
| 70 | 仿單/外盒圖檔 | ~43K | 每週 |
| 111 | QMS 製造許可 | ~10K | 每週 |
| 112 | QSD 認可登錄 | ~41K | 每週 |

下載 URL：`https://data.fda.gov.tw/data/opendata/export/{InfoId}/csv`

## 查詢優先順序

1. 判斷使用者意圖（許可證字號 / 公司名 / 製造廠 / 試劑名 / QSD / 仿單）
2. **執行檢查點**（見下節「互動檢查點」）
3. 用對應參數執行 `query_tfda.py`
4. 若查公司，自動依製造廠分組顯示
5. 若有仿單需求，補查仿單連結
6. 若涉及 QSD，檢查有效期限並標示到期警示

## 互動檢查點（Checkpoints）

在以下情境**先徵詢使用者再執行**，避免吐出無用資訊或消耗大量 token：

| 情境 | 檢查點行為 |
|------|-----------|
| 只給公司名沒給限制條件 | 先跑 `--limit 5` 預覽筆數，告知總筆數後問：「共 N 張許可證，要全部列出、還是依製造廠分組摘要？」 |
| 預估結果 > 30 筆 | 先問：「要全部顯示（可能很長）、只顯示前 20 筆、還是匯出 JSON？」 |
| QSD 查詢未指定時間範圍 | 先問：「要看全部 QSD、僅有效中、還是 6 個月內到期？」（預設：僅有效中 + 6 個月內到期標示警示） |
| 試劑名過於廣泛（如 "glucose"） | 先問：「要限定公司/廠牌嗎？還是顯示全部？」 |
| 批次仿單連結（> 10 個） | 先列出第一筆範例，問：「連結格式正確嗎？要繼續查剩下的 N 個？」 |
| 快取超過 14 天未更新 | 提醒：「快取為 YYYY-MM-DD，建議先跑 `--update-cache`，要現在更新嗎？」 |

**原則**：檢查點的目的是**省 token、省時間、提高準確度**，不是增加摩擦。單一許可證字號查詢、明確範圍的查詢不需要檢查點。

## 錯誤處理與 Fallback

查詢失敗或結果異常時，依下列順序自動 fallback，**不要直接回「查不到」就放棄**：

### 查無結果（0 筆）
1. **檢查是否全形/半形差異**：如「ARKRAY」vs「ＡＲＫＲＡＹ」，重試一次半形版本
2. **試模糊 / 關鍵字搜尋**：改用 `--keyword` 做全文搜尋（例如 `--manufacturer ARKRAY` 0 筆 → 改 `--keyword ARKRAY`）
3. **試中英文互轉**：中文廠牌查無結果時試英文（「愛科萊」→「ARKRAY」），反之亦然
4. **檢查是否打錯字**：列出資料庫中相似的名稱（編輯距離 ≤ 2），問使用者「是不是要查 XXX？」
5. **全都無解**：回報「查無資料」+ 建議（試更廣的關鍵字 / 檢查拼寫 / 確認資料來源是否有涵蓋）

### 查詢結果異常
- **筆數超過 500 筆**：自動加 `--limit 50` 並告知「共 N 筆，顯示前 50 筆，如需完整請加 --limit」
- **欄位缺失 / 空值**：用「—」或「未提供」標示，不要省略整列
- **許可證字號格式異常**：保留原始值 + 標註「格式疑似錯誤」

### 執行失敗
- **`query_tfda.py` 腳本錯誤**：先確認 Python 可用性，再看 error message 判斷是快取檔損毀、參數錯誤還是 bug
- **快取檔不存在**：自動跑 `--update-cache`，失敗則提示使用者檢查網路 / data.fda.gov.tw 可用性
- **下載資料失敗**：標註資料來源狀態，改用本地快取（即使過期也比沒有好）並警示使用者
- **組合查詢矛盾**：如 `--company A --manufacturer B` 但 A 並沒代理 B，明確回報「公司 A 目前無 B 的許可證紀錄」，不要返回空結果讓使用者誤以為腳本壞掉

## 如何執行

```bash
# 查許可證字號
python ~/.claude/skills/tfda-license-assistant/scripts/query_tfda.py --license "衛部醫器輸字第XXXXXX號"

# 查公司所有產品
python ~/.claude/skills/tfda-license-assistant/scripts/query_tfda.py --company "醫兆"

# 查製造廠/廠牌
python ~/.claude/skills/tfda-license-assistant/scripts/query_tfda.py --manufacturer "ARKRAY"

# 查試劑/檢測項目
python ~/.claude/skills/tfda-license-assistant/scripts/query_tfda.py --reagent "HbA1c"

# 全文關鍵字搜尋
python ~/.claude/skills/tfda-license-assistant/scripts/query_tfda.py --keyword "尿液分析"

# 查 QSD
python ~/.claude/skills/tfda-license-assistant/scripts/query_tfda.py --qsd "醫兆"

# 查仿單/外盒
python ~/.claude/skills/tfda-license-assistant/scripts/query_tfda.py --leaflet "衛部醫器輸字第XXXXXX號"

# 組合查詢
python ~/.claude/skills/tfda-license-assistant/scripts/query_tfda.py --company "醫兆" --manufacturer "ARKRAY"
python ~/.claude/skills/tfda-license-assistant/scripts/query_tfda.py --company "醫兆" --reagent "HbA1c"

# 輸出 JSON
python ~/.claude/skills/tfda-license-assistant/scripts/query_tfda.py --company "醫兆" --json

# 限制筆數
python ~/.claude/skills/tfda-license-assistant/scripts/query_tfda.py --company "醫兆" --limit 20

# 依製造廠分組
python ~/.claude/skills/tfda-license-assistant/scripts/query_tfda.py --reagent "glucose" --group-by manufacturer

# 更新快取
python ~/.claude/skills/tfda-license-assistant/scripts/query_tfda.py --update-cache
```

## 回答格式原則

1. 先用一句話說明查詢目標
2. 結果摘要（含分組統計，如「共 45 張許可證，ARKRAY 20 張、Sysmex 15 張、其他 10 張」）
3. Markdown 表格（依製造廠分組）
4. 仿單連結（若有查詢）
5. QSD 到期警示（若有查詢）
6. 最後附資料來源與快取日期
