"""P2.4 SKILL.md ↔ code 一致性檢查。

防止「文件承諾 vs 程式碼落差」再度發生（Phase 0 發現這是主要技術債）。

三項自動檢查：
1. SKILL.md 提到的 --flag 必須全部存在於 argparse（文件承諾必須可兌現）
2. argparse 的 --flag 必須出現在 SKILL.md（寫了功能就要文件化）
   — 允許 _DOC_OPTIONAL_FLAGS 名單豁免（內部除錯 flag）
3. SKILL.md「互動檢查點」表格提到的 flag 必須存在

這支測試 CI 必跑；失敗時同步改程式 + SKILL.md。
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SKILL_MD_PATH = ROOT / "SKILL.md"

# 允許只存在於 code 但不文件化的 flag（內部/通用）
_DOC_OPTIONAL_FLAGS = {"--cache-info"}

# 允許只存在於 SKILL.md 但暫未實作（Phase 3+ 才會做）的 flag
_CODE_OPTIONAL_FLAGS: set = set()


def _parse_skill_md_flags(text: str) -> set:
    """從 SKILL.md 全文擷取所有 --flag。"""
    return set(re.findall(r"--[a-z][a-z0-9-]+", text))


def _parse_argparse_flags() -> set:
    """實際執行 argparse build_parser() 取 flag 清單。"""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from query_tfda import build_parser
    parser = build_parser()
    flags = set()
    for action in parser._actions:
        for opt in action.option_strings:
            if opt.startswith("--"):
                flags.add(opt)
    flags.discard("--help")  # argparse 內建
    return flags


@pytest.fixture(scope="module")
def skill_md_text():
    assert SKILL_MD_PATH.exists(), f"SKILL.md 缺失：{SKILL_MD_PATH}"
    return SKILL_MD_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def skill_flags(skill_md_text):
    return _parse_skill_md_flags(skill_md_text)


@pytest.fixture(scope="module")
def code_flags():
    return _parse_argparse_flags()


def test_skill_md_flags_all_exist_in_argparse(skill_flags, code_flags):
    """SKILL.md 承諾的 flag 必須在 argparse 有對應實作。

    失敗情境：SKILL.md 新增了 --foo 但忘了實作 → 使用者會以為可用但會爆。
    """
    missing = skill_flags - code_flags - _CODE_OPTIONAL_FLAGS
    assert not missing, (
        f"SKILL.md 提到但 argparse 未實作的 flag：{sorted(missing)}\n"
        f"行動項：在 scripts/query_tfda.py build_parser() 加入這些 flag，"
        f"或從 SKILL.md 移除。"
    )


def test_argparse_flags_all_documented_in_skill_md(skill_flags, code_flags):
    """argparse 新增的 flag 必須文件化（內部 debug flag 加入 _DOC_OPTIONAL_FLAGS）。"""
    missing = code_flags - skill_flags - _DOC_OPTIONAL_FLAGS
    assert not missing, (
        f"argparse 有實作但 SKILL.md 未提及的 flag：{sorted(missing)}\n"
        f"行動項：在 SKILL.md「如何執行」區塊加範例；確為內部使用者"
        f"不需知道的，加到此測試的 _DOC_OPTIONAL_FLAGS。"
    )


def test_checkpoint_section_flags_exist_in_code(skill_md_text, code_flags):
    """互動檢查點章節裡提到的 flag 必須實作。"""
    # 擷取「互動檢查點」到下一個 ## 區段
    m = re.search(r"##\s*互動檢查點.*?(?=\n##\s)", skill_md_text, re.DOTALL)
    if not m:
        pytest.skip("SKILL.md 找不到互動檢查點章節")
    checkpoint_text = m.group(0)
    flags_in_checkpoint = _parse_skill_md_flags(checkpoint_text)
    missing = flags_in_checkpoint - code_flags
    assert not missing, (
        f"互動檢查點提到但程式未實作的 flag：{sorted(missing)}\n"
        f"這些是 SKILL 行為的核心承諾，必須實作。"
    )


def test_known_required_flags_present(code_flags):
    """合約：這幾個 flag 永遠必須存在（SKILL.md 核心功能依賴）。"""
    core = {
        "--license", "--company", "--manufacturer", "--reagent",
        "--keyword", "--qsd", "--leaflet",
        "--json", "--limit", "--group-by",
        "--update-cache",
    }
    missing = core - code_flags
    assert not missing, f"核心 flag 被刪除：{sorted(missing)}"


def test_skill_md_has_minimum_flag_coverage(skill_flags):
    """SKILL.md 至少要涵蓋核心 flag，避免文件掏空。"""
    core = {
        "--license", "--company", "--manufacturer", "--reagent",
        "--keyword", "--qsd", "--leaflet", "--update-cache",
    }
    missing = core - skill_flags
    assert not missing, f"SKILL.md 未提核心 flag：{sorted(missing)}"
