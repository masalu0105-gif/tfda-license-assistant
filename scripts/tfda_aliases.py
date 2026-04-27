"""中英文廠牌 / 公司名 alias 表讀取與展開。

設計原則：
- 外部 JSON (`aliases.json`)，alias 增補不必改 code
- 雙向對應：查 canonical 或任一 alias 都能展開整組
- 純函式，不做 I/O（載入除外）

使用方式：
    from tfda_aliases import expand_manufacturer
    expand_manufacturer("愛科萊")  # → ["愛科萊", "ARKRAY", "ARKRAY Inc.", ...]
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

_ALIAS_FILE = Path(__file__).parent / "aliases.json"


def load_aliases(path: Optional[Path] = None) -> dict:
    """載入 aliases.json。找不到檔案時回 empty dict（不 crash）。"""
    p = path or _ALIAS_FILE
    if not p.exists():
        return {"manufacturers": {}, "companies": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"manufacturers": {}, "companies": {}}


def _dedup_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        key = item.strip().lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _expand(query: str, group: Dict[str, List[str]]) -> List[str]:
    """對一個名稱與一張表，回傳其等價集合。

    匹配規則：大小寫 + 前後空白無關。
    - 命中某組（canonical 或任一 alias）→ 回傳 [canonical, *aliases]（canonical 置首）
    - 完全沒命中 → 回傳 [query]（原值，供呼叫端判斷）
    """
    if not query:
        return []
    q = query.strip().lower()
    for canonical, aliases in group.items():
        if canonical.strip().lower() == q or any(
            a.strip().lower() == q for a in aliases
        ):
            return _dedup_preserve_order([canonical] + list(aliases))
    return [query]


def expand_manufacturer(query: str, data: Optional[dict] = None) -> List[str]:
    """展開廠牌名稱的所有等價 alias。"""
    d = data if data is not None else load_aliases()
    return _expand(query, d.get("manufacturers", {}))


def expand_company(query: str, data: Optional[dict] = None) -> List[str]:
    """展開公司名稱的所有等價 alias。"""
    d = data if data is not None else load_aliases()
    return _expand(query, d.get("companies", {}))
