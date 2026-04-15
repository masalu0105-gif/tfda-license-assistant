---
name: tfda-license-assistant
description: |
  查詢台灣衛福部 TFDA 醫療器材公開資料：許可證、QSD/QMS 登錄、仿單/外盒圖檔。
  支援依公司名稱、許可證字號、製造廠/廠牌、試劑名稱、檢測項目等條件查詢。
  適合醫療器材代理商業務人員日常使用。
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
