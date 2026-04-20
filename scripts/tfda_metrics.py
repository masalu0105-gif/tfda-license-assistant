"""每次 CLI 執行追加一筆 JSON 到 metrics.jsonl，供事後分析。

設計原則：
- PII-free：查詢字串預設不記；使用者明確指定 --log-query 才記
- 追加式（append-only）不讀取歷史，避免鎖競爭
- 純 stdlib，不引入相依

Schema (每行一筆 JSON)：
  ts              ISO8601 timestamp
  query_type      "company" / "manufacturer" / "qsd" / "leaflet" /
                  "license" / "cache_info" / "update_cache" / "help"
  result_count    回傳筆數
  duration_ms     CLI 總執行時間
  fallback_used   觸發的 fallback（alias / suggest / offline），list
  cache_age_hours 使用的快取年齡（若可取得）
  query           查詢字串（僅 --log-query 時）

分析用途：
- alias / suggest 觸發率 → 決定是否擴充 aliases.json
- p95 duration → 決定是否需要 Phase 5 的 pre-index
- 快取新鮮度分布
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

log = logging.getLogger("tfda")


def get_metrics_path() -> Path:
    """取得 metrics.jsonl 預設路徑（可被測試 monkeypatch）。"""
    return Path.home() / ".cache" / "tfda" / "metrics.jsonl"


def record(
    query_type: str,
    result_count: int = 0,
    duration_ms: float = 0.0,
    fallback_used: Optional[List[str]] = None,
    cache_age_hours: Optional[float] = None,
    query: Optional[str] = None,
    metrics_file: Optional[Path] = None,
) -> None:
    """追加一筆 metric 到 jsonl。寫入失敗不 raise（觀察性不應影響主流程）。"""
    try:
        path = metrics_file or get_metrics_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now().isoformat(),
            "query_type": query_type,
            "result_count": int(result_count),
            "duration_ms": round(float(duration_ms), 1),
            "fallback_used": list(fallback_used or []),
        }
        if cache_age_hours is not None:
            entry["cache_age_hours"] = round(float(cache_age_hours), 1)
        if query is not None:
            entry["query"] = query
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:  # pragma: no cover - 防禦性
        log.debug("metrics 寫入失敗（非致命）：%s", e)
