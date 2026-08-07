# pyright: basic
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from ame_ai_review_system import payload as payload_module
from ame_ai_review_system.payload import (
    _primary_diff_text,
    build_valid_lines_map,
    parse_review_json,
    parse_review_json_with_flag,
)


def test_parse_review_json_plain(tmp_path: Path) -> None:
    data = {
        "summary": "Good progress.",
        "comments": [],
    }
    tmp_file = tmp_path / "review.json"
    tmp_file.write_text(json.dumps(data), encoding="utf-8")

    res = parse_review_json(str(tmp_file))
    assert res["summary"] == "Good progress."
    assert res["comments"] == []


def test_parse_review_json_with_code_fence(tmp_path: Path) -> None:
    raw_content = """Some text before
```json
{
  "summary": "Code fence test",
  "comments": []
}
```
Some text after"""
    tmp_file = tmp_path / "review.json"
    tmp_file.write_text(raw_content, encoding="utf-8")

    res = parse_review_json(str(tmp_file))
    assert res["summary"] == "Code fence test"
    assert res["comments"] == []


def test_parse_review_json_fallback_on_invalid(tmp_path: Path) -> None:
    tmp_file = tmp_path / "broken.json"
    tmp_file.write_text("not a json content at all", encoding="utf-8")

    res, is_fallback = parse_review_json_with_flag(str(tmp_file))
    assert is_fallback is True
    assert res["comments"] == []


def test_parse_review_json_with_flag_false_on_valid(tmp_path: Path) -> None:
    data = {"summary": "LGTM", "comments": []}
    tmp_file = tmp_path / "review.json"
    tmp_file.write_text(json.dumps(data), encoding="utf-8")

    res, is_fallback = parse_review_json_with_flag(str(tmp_file))
    assert is_fallback is False
    assert res["summary"] == "LGTM"


def test_parse_review_json_repair_fixes_broken_output(tmp_path: Path) -> None:
    broken = (
        '<invoke name="bash">\n'
        "git status\n"
        "</invoke>\n"
        '{"summary": "repaired", "comments": []}\n'
        "trailing text"
    )
    tmp_file = tmp_path / "broken.json"
    tmp_file.write_text(broken, encoding="utf-8")

    def _repair(raw: str) -> str | None:
        assert "git status" in raw
        return '{"summary": "repaired", "comments": []}'

    res, is_fallback = parse_review_json_with_flag(str(tmp_file), repair=_repair)
    assert is_fallback is False
    assert res["summary"] == "repaired"


def test_parse_review_json_repair_none_keeps_fallback(tmp_path: Path) -> None:
    tmp_file = tmp_path / "broken.json"
    tmp_file.write_text("not a json content at all", encoding="utf-8")

    res, is_fallback = parse_review_json_with_flag(
        str(tmp_file),
        repair=lambda _raw: None,
    )
    assert is_fallback is True
    assert res["comments"] == []


def test_parse_review_json_repair_retries_on_broken_first_attempt(
    tmp_path: Path,
) -> None:
    tmp_file = tmp_path / "broken.json"
    tmp_file.write_text("not a json content at all", encoding="utf-8")

    calls = {"n": 0}

    def _repair(_raw: str) -> str | None:
        calls["n"] += 1
        if calls["n"] < 2:
            return "still broken"
        return '{"summary": "recovered", "comments": []}'

    res, is_fallback = parse_review_json_with_flag(str(tmp_file), repair=_repair)
    assert is_fallback is False
    assert res["summary"] == "recovered"
    assert calls["n"] == 2


def test_structural_repair_preserves_fullwidth_bars_in_repair_input(
    tmp_path: Path,
) -> None:
    # ツール呼び出しブロックを含まない壊れ出力では全幅マーカー除去を適用せず、
    # JSON 本文の全幅縦棒 (Markdown 装飾等) を修復入力へそのまま渡す。
    broken = '{"summary": "a \uff5c b", "comments": []'
    tmp_file = tmp_path / "broken.json"
    tmp_file.write_text(broken, encoding="utf-8")

    received: dict[str, str] = {}

    def _repair(raw: str) -> str | None:
        received["raw"] = raw
        return '{"summary": "fixed", "comments": []}'

    res, is_fallback = parse_review_json_with_flag(str(tmp_file), repair=_repair)
    assert is_fallback is False
    assert res["summary"] == "fixed"
    assert "\uff5c" in received["raw"]


def test_parse_review_json_structural_repair_without_llm(tmp_path: Path) -> None:
    # ツール呼び出しブロック内の「{」によりブレーススキャンが失敗し、
    # 構造的修復 (ツール呼び出し構文の除去) が実際に駆動されることを確認する。
    broken = (
        "<tool_calls>\n"
        '<invoke name="bash">\n'
        "echo '{\n"
        "</invoke>\n"
        "</tool_calls>\n"
        '{"summary": "structural", "comments": []}\n'
    )
    tmp_file = tmp_path / "broken.json"
    tmp_file.write_text(broken, encoding="utf-8")

    called = {"llm": False}

    def _repair(_raw: str) -> str | None:
        called["llm"] = True
        return None

    res, is_fallback = parse_review_json_with_flag(str(tmp_file), repair=_repair)
    assert is_fallback is False
    assert res["summary"] == "structural"
    assert called["llm"] is False


def test_parse_review_json_max_attempts_respected(tmp_path: Path) -> None:
    # Issue #65: max_attempts で修復試行回数を制限できる。
    tmp_file = tmp_path / "broken.json"
    tmp_file.write_text("not a json content at all", encoding="utf-8")

    calls = {"n": 0}

    def _repair(_raw: str) -> str | None:
        calls["n"] += 1
        return "still broken"

    _res, is_fallback = parse_review_json_with_flag(
        str(tmp_file),
        repair=_repair,
        max_attempts=5,
    )
    assert is_fallback is True
    assert calls["n"] == 5


def test_parse_review_json_default_attempts_is_three(tmp_path: Path) -> None:
    # Issue #65: 省略時は 3 回 (従来 2 から引き上げ)。
    tmp_file = tmp_path / "broken.json"
    tmp_file.write_text("not a json content at all", encoding="utf-8")

    calls = {"n": 0}

    def _repair(_raw: str) -> str | None:
        calls["n"] += 1
        return "still broken"

    _res, _is_fallback = parse_review_json_with_flag(str(tmp_file), repair=_repair)
    assert calls["n"] == 3


def test_build_payloads_omits_reviewed_sha_on_fallback() -> None:
    # Issue #65: パース失敗時は reviewed-sha マーカーを付けず再レビューを可能にする。
    from ame_ai_review_system.payload import build_review_payloads

    fallback = {"summary": "parse failed", "comments": []}
    payloads = build_review_payloads(fallback, {}, "abc123", is_fallback=True)
    assert len(payloads) == 1
    assert "reviewed-sha" not in payloads[0]["body"]


def test_build_payloads_keeps_reviewed_sha_on_success() -> None:
    from ame_ai_review_system.payload import build_review_payloads

    review = {"summary": "LGTM", "comments": []}
    payloads = build_review_payloads(review, {}, "abc123", is_fallback=False)
    assert "reviewed-sha: abc123" in payloads[0]["body"]


def test_build_repair_prompt_sanitizes_fence() -> None:
    from ame_ai_review_system.payload import build_repair_prompt

    broken = '前書き\n```json\n{"summary": "x"}\n```\n後書き'
    prompt = build_repair_prompt(broken)
    assert "```json" not in prompt
    assert "\u00b7\u00b7\u00b7json" in prompt
    assert prompt.count("```") == 2


# ---------------------------
# build_valid_lines_map / _primary_diff_text (Issue #55)
# ---------------------------


def test_primary_diff_text_uses_base_range(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_check_output(cmd: list[str], **kw: Any) -> str:
        captured["cmd"] = cmd
        return "diff content"

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    assert _primary_diff_text("main") == "diff content"
    assert captured["cmd"] == ["git", "diff", "origin/main...HEAD"]


def test_primary_diff_text_falls_back_to_head_prev(monkeypatch: Any) -> None:
    # リモート追跡 ref が無い環境では HEAD~1 にフォールバックし、
    # build_valid_lines_map が {} にならずインラインスレッドを作れるようにする。
    calls: list[list[str]] = []

    def fake_check_output(cmd: list[str], **kw: Any) -> str:
        calls.append(cmd)
        if cmd[2].startswith("origin/"):
            raise subprocess.CalledProcessError(128, cmd)
        return "fallback diff"

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    assert _primary_diff_text("main") == "fallback diff"
    assert calls[-1] == ["git", "diff", "HEAD~1"]


def test_primary_diff_text_empty_when_all_fail(monkeypatch: Any) -> None:
    def fake_check_output(cmd: list[str], **kw: Any) -> str:
        raise subprocess.CalledProcessError(128, cmd)

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    assert not _primary_diff_text("main")


def test_build_valid_lines_map_parses_added_lines(monkeypatch: Any) -> None:
    diff = (
        "diff --git a/src/app.py b/src/app.py\n"
        "index 000..111 100644\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -10,3 +10,4 @@ def main():\n"
        "     existing\n"
        "+added_line\n"
        "     kept\n"
    )
    monkeypatch.setattr(payload_module, "_primary_diff_text", lambda _base: diff)
    # ハンク内の追加行 + コンテキスト行はインラインコメントの有効位置。
    assert build_valid_lines_map("main") == {"src/app.py": {10, 11, 12}}


def test_build_valid_lines_map_empty_on_no_diff(monkeypatch: Any) -> None:
    monkeypatch.setattr(payload_module, "_primary_diff_text", lambda _base: "")
    assert build_valid_lines_map("main") == {}
