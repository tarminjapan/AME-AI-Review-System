# pyright: basic
from __future__ import annotations

from typing import Any

import pytest
from ame_ai_review_system import github_client, reply
from ame_ai_review_system.reply import _extract_json, _group_by_thread
from ame_ai_review_system.stale_detect import is_stale_loop


def test_extract_json_plain() -> None:
    raw = '{"lgtm": true, "reply": "Looks clean!"}'
    res = _extract_json(raw)
    assert res is not None
    assert res.get("lgtm") is True
    assert res.get("reply") == "Looks clean!"


def test_extract_json_with_code_fence() -> None:
    raw = """Here is the result:
```json
{"lgtm": false, "reply": "Please fix line 10"}
```"""
    res = _extract_json(raw)
    assert res is not None
    assert res.get("lgtm") is False
    assert res.get("reply") == "Please fix line 10"


# --- is_stale_loop --------------------------------------------------------


def test_stale_loop_empty_list() -> None:
    assert is_stale_loop([]) is False


def test_stale_loop_single_comment() -> None:
    assert is_stale_loop(["one comment"]) is False


def test_stale_loop_identical_long_comments() -> None:
    body = "この関数は例外をキャッチしていません 修正してください"
    assert is_stale_loop([body, body]) is True


def test_stale_loop_high_similarity() -> None:
    c1 = "この関数は例外をキャッチしていません 修正してください"
    c2 = "この関数は例外をキャッチしていません 修正してください。"
    assert is_stale_loop([c1, c2]) is True


def test_stale_loop_low_similarity() -> None:
    c1 = "この関数は例外をキャッチしていません 修正してください"
    c2 = "変数名が不適切です snake_case を使ってください"
    assert is_stale_loop([c1, c2]) is False


def test_stale_loop_short_exact_match() -> None:
    assert is_stale_loop(["LGTM", "LGTM"]) is True


def test_stale_loop_short_different() -> None:
    assert is_stale_loop(["LGTM", "Fix it"]) is False


def test_stale_loop_empty_bodies() -> None:
    assert is_stale_loop(["", ""]) is False


# --- is_stale_loop threshold (Issue #67) ---------------------------------


def test_stale_loop_threshold_override_detects_lower_similarity() -> None:
    # デフォルト 0.80 では非 stale だが、閾値を下げると stale 判定される組。
    c1 = "この関数は例外をキャッチしていません 修正してください"
    c2 = "この関数は例外処理が不足しています 直してください"
    assert is_stale_loop([c1, c2]) is False
    assert is_stale_loop([c1, c2], threshold=0.25) is True


def test_stale_loop_threshold_none_uses_default() -> None:
    body = "この関数は例外をキャッチしていません 修正してください"
    assert is_stale_loop([body, body], threshold=None) is True


# --- _group_by_thread (GitHub flat comments API) ---------------------------


def _comment(
    cid: int,
    body: str = "",
    *,
    in_reply_to: int | None = None,
    created_at: str = "2024-01-01T00:00:00Z",
    login: str = "octocat",
    path: str = "src/app.py",
) -> dict[str, Any]:
    return {
        "id": cid,
        "in_reply_to_id": in_reply_to,
        "body": body,
        "created_at": created_at,
        "user": {"login": login},
        "path": path,
    }


def test_group_by_thread_single_root() -> None:
    comments = [_comment(1, "root"), _comment(2, "reply1", in_reply_to=1)]
    grouped = _group_by_thread(comments)
    assert set(grouped.keys()) == {1}
    assert [c["id"] for c in grouped[1]] == [1, 2]


def test_group_by_thread_multiple_threads() -> None:
    comments = [
        _comment(10, "rootA"),
        _comment(20, "rootB"),
        _comment(11, "a1", in_reply_to=10),
        _comment(21, "b1", in_reply_to=20),
        _comment(12, "a2", in_reply_to=10),
    ]
    grouped = _group_by_thread(comments)
    assert set(grouped.keys()) == {10, 20}
    assert [c["id"] for c in grouped[10]] == [10, 11, 12]
    assert [c["id"] for c in grouped[20]] == [20, 21]


def test_group_by_thread_orders_by_created_at() -> None:
    comments = [
        _comment(1, "root", created_at="2024-01-01T00:00:00Z"),
        _comment(3, "late", in_reply_to=1, created_at="2024-01-03T00:00:00Z"),
        _comment(2, "early", in_reply_to=1, created_at="2024-01-02T00:00:00Z"),
    ]
    grouped = _group_by_thread(comments)
    assert [c["id"] for c in grouped[1]] == [1, 2, 3]


def test_group_by_thread_orphan_reply_ignored() -> None:
    """in_reply_to_id が現在のページに無いルートを指す場合は単独スレッドを形成しない."""
    comments = [_comment(99, "orphan reply", in_reply_to=9999)]
    grouped = _group_by_thread(comments)
    # 99 自身は親を持つため root として扱われない。result は空になる。
    assert grouped == {}


# --- _root_id_for_comment -------------------------------------------------


def test_root_id_for_comment_finds_thread() -> None:
    comments = [
        _comment(10, "rootA"),
        _comment(20, "rootB"),
        _comment(11, "a1", in_reply_to=10),
        _comment(12, "a2", in_reply_to=10),
        _comment(21, "b1", in_reply_to=20),
    ]
    assert reply._root_id_for_comment(comments, 11) == 10
    assert reply._root_id_for_comment(comments, 12) == 10
    assert reply._root_id_for_comment(comments, 21) == 20


def test_root_id_for_comment_root_itself() -> None:
    comments = [_comment(10, "rootA"), _comment(11, "a1", in_reply_to=10)]
    assert reply._root_id_for_comment(comments, 10) == 10


def test_root_id_for_comment_unknown_returns_none() -> None:
    """非インラインコメント（PR 本文コメント等）は None を返す."""
    comments = [_comment(10, "rootA")]
    assert reply._root_id_for_comment(comments, 999) is None


# --- _thread_is_pending ---------------------------------------------------


def _thread_is_pending_for(thread: list[dict[str, Any]]) -> bool:
    return reply._thread_is_pending(
        int(thread[0]["id"]), thread, set(), "ame-ai-reviewer"
    )


def test_thread_is_pending_with_mention() -> None:
    thread = [
        _comment(10, "root", login="ame-ai-reviewer[bot]"),
        _comment(11, "@ame-ai-reviewer 修正しました", login="octocat"),
    ]
    assert _thread_is_pending_for(thread) is True


def test_thread_is_pending_without_mention() -> None:
    thread = [
        _comment(10, "root", login="ame-ai-reviewer[bot]"),
        _comment(11, "修正しました", login="octocat"),
    ]
    assert _thread_is_pending_for(thread) is False


def test_thread_is_pending_after_reviewer_reply() -> None:
    thread = [
        _comment(10, "root", login="ame-ai-reviewer[bot]"),
        _comment(11, "@ame-ai-reviewer 修正しました", login="octocat"),
        _comment(
            12,
            "対応確認しました。LGTM ✅",
            login="ame-ai-reviewer[bot]",
            created_at="2024-01-02T00:00:00Z",
        ),
    ]
    assert _thread_is_pending_for(thread) is False


def test_thread_is_pending_resolved() -> None:
    thread = [
        _comment(10, "root", login="ame-ai-reviewer[bot]"),
        _comment(11, "@ame-ai-reviewer 修正しました", login="octocat"),
    ]
    assert reply._thread_is_pending(10, thread, {10}, "ame-ai-reviewer") is False


# --- _resolved_root_ids (GraphQL isResolved integration) ------------------


def test_resolved_root_ids_collects_resolved_thread_members(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    threads = [
        {
            "id": "T1",
            "isResolved": True,
            "comments": {"nodes": [{"databaseId": 100}, {"databaseId": 101}]},
        },
        {
            "id": "T2",
            "isResolved": False,
            "comments": {"nodes": [{"databaseId": 200}]},
        },
        {
            "id": "T3",
            "isResolved": True,
            "comments": {"nodes": [{"databaseId": 300}]},
        },
    ]
    monkeypatch.setattr(github_client, "list_review_threads", lambda _pr, _tok: threads)
    result = reply._resolved_root_ids(7, "tok")
    assert result == {100, 101, 300}


def test_resolved_root_ids_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(github_client, "list_review_threads", lambda _pr, _tok: [])
    assert reply._resolved_root_ids(7, "tok") == set()


# --- GitHub App [bot] suffix integration ----------------------------------


def test_mention_detection_accepts_bot_form() -> None:
    """reviewer_name='ame-ai-reviewer' でも @ame-ai-reviewer[bot] を検出できることを検証する。."""
    assert github_client.mentions_reviewer(
        "@ame-ai-reviewer[bot] 修正しました", "ame-ai-reviewer"
    )


def test_mention_detection_accepts_short_form() -> None:
    """後方互換のため @ame-ai-reviewer (短縮形) も検出することを検証する。."""
    assert github_client.mentions_reviewer(
        "@ame-ai-reviewer 修正しました", "ame-ai-reviewer"
    )


def test_mention_detection_rejects_unrelated_mention() -> None:
    """無関係なメンションは拒否することを検証する。."""
    assert not github_client.mentions_reviewer(
        "@other-user 修正しました", "ame-ai-reviewer"
    )


# --- _cmd_run scoped mode (TRIGGER_COMMENT_ID) ----------------------------


def _patch_cmd_run(
    monkeypatch: pytest.MonkeyPatch, comments: list[dict[str, Any]]
) -> list[int]:
    monkeypatch.setattr(
        github_client, "resolve_env", lambda: ("https://api.github.com", "octo/repo")
    )
    monkeypatch.setattr(reply, "_get_thread_comments", lambda *_args: comments)
    monkeypatch.setattr(reply, "_resolved_root_ids", lambda *_args: set())
    processed: list[int] = []
    monkeypatch.setattr(
        reply, "_process_thread", lambda *args, **_kwargs: processed.append(args[3])
    )
    monkeypatch.setenv("REVIEWER_TOKEN", "tok")
    return processed


def test_cmd_run_scoped_processes_only_trigger_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TRIGGER_COMMENT_ID で指したスレッドだけを処理する (Issue #39)."""
    comments = [
        _comment(10, "rootA", login="ame-ai-reviewer[bot]"),
        _comment(11, "@ame-ai-reviewer 修正しました", login="octocat", in_reply_to=10),
        _comment(20, "rootB", login="ame-ai-reviewer[bot]"),
        _comment(21, "@ame-ai-reviewer 修正しました", login="octocat", in_reply_to=20),
    ]
    processed = _patch_cmd_run(monkeypatch, comments)
    monkeypatch.setenv("TRIGGER_COMMENT_ID", "11")
    reply._cmd_run("7")
    assert processed == [10]


def test_cmd_run_scoped_unknown_comment_skips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """非インラインのトリガーコメントでは何も処理しない."""
    comments = [_comment(10, "rootA", login="ame-ai-reviewer[bot]")]
    processed = _patch_cmd_run(monkeypatch, comments)
    monkeypatch.setenv("TRIGGER_COMMENT_ID", "999")
    reply._cmd_run("7")
    assert processed == []


def test_cmd_run_scoped_delegates_pending_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """保留判定は _process_thread へ委譲し、_cmd_run では二重チェックしない."""
    comments = [
        _comment(10, "rootA", login="ame-ai-reviewer[bot]"),
        _comment(11, "@ame-ai-reviewer 修正しました", login="octocat", in_reply_to=10),
        _comment(
            12,
            "対応確認しました。LGTM ✅",
            login="ame-ai-reviewer[bot]",
            created_at="2024-01-02T00:00:00Z",
            in_reply_to=10,
        ),
    ]
    processed = _patch_cmd_run(monkeypatch, comments)
    monkeypatch.setenv("TRIGGER_COMMENT_ID", "11")
    reply._cmd_run("7")
    assert processed == [10]


def test_cmd_run_legacy_scan_all_when_no_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TRIGGER_COMMENT_ID 未設定時は全保留スレッドを処理する (後方互換)."""
    monkeypatch.setattr(
        github_client, "resolve_env", lambda: ("https://api.github.com", "octo/repo")
    )
    monkeypatch.setattr(reply, "_get_pending_threads", lambda *_args: [10, 20])
    processed: list[int] = []
    monkeypatch.setattr(
        reply, "_process_thread", lambda *args, **_kwargs: processed.append(args[3])
    )
    monkeypatch.setenv("REVIEWER_TOKEN", "tok")
    monkeypatch.delenv("TRIGGER_COMMENT_ID", raising=False)
    reply._cmd_run("7")
    assert processed == [10, 20]


# --- _process_thread (投稿前再チェック) ------------------------------------


def test_process_thread_skips_when_not_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """スレッドが最初から保留でなければ投稿しない."""
    monkeypatch.setattr(reply, "_thread_still_pending", lambda *_args: False)
    bodies: list[str] = []

    def record_post(*args: object) -> int:
        bodies.append(str(args[5]))
        return 200

    monkeypatch.setattr(reply, "_post_reply", record_post)
    monkeypatch.setattr(reply, "_check_stale", lambda *_args: "ok")
    reply._process_thread("api", "octo/repo", 7, 10, "tok", "ame-ai-reviewer", "main")
    assert bodies == []


def test_process_thread_posts_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reply, "_thread_still_pending", lambda *_args: True)
    bodies: list[str] = []

    def record_post(*args: object) -> int:
        bodies.append(str(args[5]))
        return 200

    monkeypatch.setattr(reply, "_post_reply", record_post)
    monkeypatch.setattr(reply, "_check_stale", lambda *_args: "ok")
    monkeypatch.setattr(reply, "_build_prompt_for_thread", lambda *_args: "prompt")
    monkeypatch.setattr(
        reply,
        "_run_engine",
        lambda *_args, **_kwargs: (0, '{"lgtm": true, "reply": "LGTM"}'),
    )
    reply._process_thread("api", "octo/repo", 7, 10, "tok", "ame-ai-reviewer", "main")
    assert bodies == ["LGTM"]


def test_process_thread_skips_when_no_longer_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """エンジン実行後にスレッドが非保留化していたら投稿しない (競合負け)."""
    calls = {"n": 0}

    def still_pending(*_args: object) -> bool:
        calls["n"] += 1
        return calls["n"] < 2  # 初回は True、投稿直前は False

    monkeypatch.setattr(reply, "_thread_still_pending", still_pending)
    bodies: list[str] = []

    def record_post(*args: object) -> int:
        bodies.append(str(args[5]))
        return 200

    monkeypatch.setattr(reply, "_post_reply", record_post)
    monkeypatch.setattr(reply, "_check_stale", lambda *_args: "ok")
    monkeypatch.setattr(reply, "_build_prompt_for_thread", lambda *_args: "prompt")
    monkeypatch.setattr(
        reply,
        "_run_engine",
        lambda *_args, **_kwargs: (0, '{"lgtm": true, "reply": "LGTM"}'),
    )
    reply._process_thread("api", "octo/repo", 7, 10, "tok", "ame-ai-reviewer", "main")
    assert bodies == []


# --- engine info injection sentinel (Issue #40) -----------------------------


def test_run_engine_injects_show_info_by_default(
    capture_engine_env: dict[str, Any],
) -> None:
    # 哨戒テスト: 既定 (show_info=True) では子プロセスへ表示フラグを注入する (Issue #40)。
    reply._run_engine("PROMPT")
    assert capture_engine_env["env"].get("AME_ENGINE_SHOW_INFO") == "1"


def test_run_engine_omits_show_info_when_gate2_false(
    capture_engine_env: dict[str, Any],
) -> None:
    reply._run_engine("PROMPT", show_info=False)
    assert capture_engine_env["env"].get("AME_ENGINE_SHOW_INFO") == "0"
