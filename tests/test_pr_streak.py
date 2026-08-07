# pyright: basic
from __future__ import annotations

import json
import os
import pathlib
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from ame_ai_review_system import github_client, pr_streak
from ame_ai_review_system.pr_streak import (
    _current_head_sha as current_head_sha,
)
from ame_ai_review_system.pr_streak import (
    _find_streak_comment as find_streak_comment,
)
from ame_ai_review_system.pr_streak import (
    _is_blocking as is_blocking,
)
from ame_ai_review_system.pr_streak import (
    _pr_comments_url as pr_comments_url,
)
from ame_ai_review_system.pr_streak import (
    _token as token,
)

if TYPE_CHECKING:
    import pytest

# ---------------------------
# _find_streak_comment
# ---------------------------


def test_find_streak_comment_detects_marker() -> None:
    comments = [
        {"id": 10, "body": "regular comment"},
        {"id": 20, "body": "<!-- ai-review-streak -->\nstreak: 2"},
    ]
    result = find_streak_comment(comments)
    assert result is not None
    assert result[0] == 20
    assert result[1] == 2


def test_find_streak_comment_returns_none_when_absent() -> None:
    comments = [{"id": 1, "body": "no marker here"}]
    assert find_streak_comment(comments) is None


def test_find_streak_comment_extracts_head_sha() -> None:
    comments = [
        {
            "id": 5,
            "body": "<!-- ai-review-streak -->\nstreak: 3\nhead: abc123def",
        },
    ]
    result = find_streak_comment(comments)
    assert result is not None
    assert result[2] == "abc123def"


def test_find_streak_comment_empty_head_when_missing() -> None:
    comments = [
        {"id": 5, "body": "<!-- ai-review-streak -->\nstreak: 1"},
    ]
    result = find_streak_comment(comments)
    assert result is not None
    assert not result[2]


def test_find_streak_comment_picks_latest() -> None:
    comments = [
        {"id": 1, "body": "<!-- ai-review-streak -->\nstreak: 1"},
        {"id": 2, "body": "<!-- ai-review-streak -->\nstreak: 3"},
    ]
    result = find_streak_comment(comments)
    assert result is not None
    assert result[0] == 2
    assert result[1] == 3


def test_find_streak_comment_skips_missing_id() -> None:
    comments: list[dict[str, Any]] = [
        {"body": "<!-- ai-review-streak -->\nstreak: 2"},
        {"id": 10, "body": "<!-- ai-review-streak -->\nstreak: 1"},
    ]
    result = find_streak_comment(comments)
    assert result is not None
    assert result[0] == 10


# ---------------------------
# _is_blocking
# ---------------------------


def test_is_blocking_true_for_high() -> None:
    assert is_blocking({"severity": "HIGH"})


def test_is_blocking_false_for_low() -> None:
    assert not is_blocking({"severity": "LOW"})


def test_is_blocking_false_for_info() -> None:
    assert not is_blocking({"severity": "INFO"})


def test_is_blocking_true_for_unknown() -> None:
    assert is_blocking({"severity": "UNKNOWN"})


def test_is_blocking_true_for_empty() -> None:
    assert is_blocking({})


# ---------------------------
# _current_head_sha
# ---------------------------


def test_current_head_sha_returns_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_a, **_kw: SimpleNamespace(stdout="abc123\n"),
    )
    assert current_head_sha() == "abc123"


def test_current_head_sha_empty_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_a: Any, **_kw: Any) -> Any:
        raise subprocess.SubprocessError

    monkeypatch.setattr(subprocess, "run", _raise)
    assert not current_head_sha()


# ---------------------------
# _pr_comments_url (pagination)
# ---------------------------


def test_pr_comments_url_includes_limit() -> None:
    url = pr_comments_url(42, "https://api.github.com", "Org/Repo")
    assert "per_page=" in url


# ---------------------------
# cmd_get
# ---------------------------


def test_cmd_get_prints_streak(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(pr_streak, "_token", lambda: "fake")
    monkeypatch.setattr(
        pr_streak,
        "_github_env",
        lambda: ("https://api.github.com", "Org/Repo"),
    )
    monkeypatch.setattr(
        pr_streak,
        "_read_pr_comments",
        lambda *_: [{"id": 1, "body": "<!-- ai-review-streak -->\nstreak: 2"}],
    )
    rc = pr_streak.cmd_get(1)
    assert rc == 0
    assert capsys.readouterr().out.strip() == "2"


def test_cmd_get_no_token_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pr_streak, "_token", lambda: "")
    assert pr_streak.cmd_get(1) == 1


def test_cmd_get_no_marker_prints_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(pr_streak, "_token", lambda: "fake")
    monkeypatch.setattr(pr_streak, "_github_env", lambda: ("https://u", "r"))
    monkeypatch.setattr(pr_streak, "_read_pr_comments", lambda *_: [])
    rc = pr_streak.cmd_get(1)
    assert rc == 0
    assert capsys.readouterr().out.strip() == "0"


# ---------------------------
# cmd_check
# ---------------------------


def test_cmd_check_approved_when_streak_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pr_streak, "_token", lambda: "fake")
    monkeypatch.setattr(pr_streak, "_github_env", lambda: ("https://u", "r"))
    monkeypatch.setattr(
        pr_streak,
        "_read_pr_comments",
        lambda *_: [{"id": 1, "body": "<!-- ai-review-streak -->\nstreak: 2"}],
    )
    monkeypatch.setattr(pr_streak, "_current_head_sha", lambda: "")
    assert pr_streak.cmd_check(1) == 0


def test_cmd_check_blocks_when_streak_below_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pr_streak, "_token", lambda: "fake")
    monkeypatch.setattr(pr_streak, "_github_env", lambda: ("https://u", "r"))
    monkeypatch.setattr(
        pr_streak,
        "_read_pr_comments",
        lambda *_: [{"id": 1, "body": "<!-- ai-review-streak -->\nstreak: 1"}],
    )
    assert pr_streak.cmd_check(1) == 1


def test_cmd_check_blocks_on_new_push(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pr_streak, "_token", lambda: "fake")
    monkeypatch.setattr(pr_streak, "_github_env", lambda: ("https://u", "r"))
    monkeypatch.setattr(
        pr_streak,
        "_read_pr_comments",
        lambda *_: [
            {
                "id": 1,
                "body": "<!-- ai-review-streak -->\nstreak: 2\nhead: abc123",
            },
        ],
    )
    monkeypatch.setattr(pr_streak, "_current_head_sha", lambda: "def456")
    assert pr_streak.cmd_check(1) == 1


def test_cmd_check_passes_when_head_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pr_streak, "_token", lambda: "fake")
    monkeypatch.setattr(pr_streak, "_github_env", lambda: ("https://u", "r"))
    monkeypatch.setattr(
        pr_streak,
        "_read_pr_comments",
        lambda *_: [
            {
                "id": 1,
                "body": "<!-- ai-review-streak -->\nstreak: 2\nhead: abc123",
            },
        ],
    )
    monkeypatch.setattr(pr_streak, "_current_head_sha", lambda: "abc123")
    assert pr_streak.cmd_check(1) == 0


def test_cmd_check_no_token_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pr_streak, "_token", lambda: "")
    assert pr_streak.cmd_check(1) == 1


# ---------------------------
# cmd_evaluate
# ---------------------------


def _write_review(tmp_path: Path, review: dict[str, Any]) -> str:
    p = tmp_path / "review.json"
    p.write_text(json.dumps(review), encoding="utf-8")
    return str(p)


def test_cmd_evaluate_zero_issues_passes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(pr_streak, "_token", lambda: "fake")
    monkeypatch.setattr(pr_streak, "_github_env", lambda: ("https://u", "r"))
    monkeypatch.setattr(pr_streak, "_read_pr_comments", lambda *_: [])
    monkeypatch.setattr(pr_streak, "cmd_set", lambda *_a, **_kw: 0)
    review_path = _write_review(tmp_path, {"summary": "ok", "comments": []})
    rc = pr_streak.cmd_evaluate(1, review_path)
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["allow"] is True
    assert out["streak"] == 0


def test_cmd_evaluate_blocking_resets_streak(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(pr_streak, "_token", lambda: "fake")
    monkeypatch.setattr(pr_streak, "_github_env", lambda: ("https://u", "r"))
    monkeypatch.setattr(pr_streak, "_read_pr_comments", lambda *_: [])
    monkeypatch.setattr(pr_streak, "cmd_set", lambda *_a, **_kw: 0)
    review_path = _write_review(
        tmp_path,
        {
            "summary": "blocking",
            "comments": [{"severity": "HIGH", "path": "a", "line": 1}],
        },
    )
    rc = pr_streak.cmd_evaluate(1, review_path)
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["allow"] is False
    assert out["streak"] == 0


def test_cmd_evaluate_low_only_increments_streak(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(pr_streak, "_token", lambda: "fake")
    monkeypatch.setattr(pr_streak, "_github_env", lambda: ("https://u", "r"))
    monkeypatch.setattr(
        pr_streak,
        "_read_pr_comments",
        lambda *_: [{"id": 1, "body": "<!-- ai-review-streak -->\nstreak: 0"}],
    )
    monkeypatch.setattr(pr_streak, "cmd_set", lambda *_a, **_kw: 0)
    review_path = _write_review(
        tmp_path,
        {
            "summary": "low",
            "comments": [{"severity": "LOW", "path": "a", "line": 1}],
        },
    )
    rc = pr_streak.cmd_evaluate(1, review_path)
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["allow"] is False
    assert out["streak"] == 1


def test_cmd_evaluate_low_only_at_threshold_passes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(pr_streak, "_token", lambda: "fake")
    monkeypatch.setattr(pr_streak, "_github_env", lambda: ("https://u", "r"))
    monkeypatch.setattr(
        pr_streak,
        "_read_pr_comments",
        lambda *_: [{"id": 1, "body": "<!-- ai-review-streak -->\nstreak: 1"}],
    )
    monkeypatch.setattr(pr_streak, "cmd_set", lambda *_a, **_kw: 0)
    review_path = _write_review(
        tmp_path,
        {
            "summary": "low 2nd",
            "comments": [{"severity": "LOW", "path": "a", "line": 1}],
        },
    )
    rc = pr_streak.cmd_evaluate(1, review_path)
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["allow"] is True
    assert out["streak"] == 2


def test_cmd_evaluate_fallback_json_blocks(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    review_path = tmp_path / "review.json"
    review_path.write_text("not valid json", encoding="utf-8")
    rc = pr_streak.cmd_evaluate(1, str(review_path))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["allow"] is False


# ---------------------------
# cmd_set (head SHA)
# ---------------------------


def test_cmd_set_includes_head_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        url: str,
        _token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> dict[str, Any]:
        captured["method"] = method
        captured["url"] = url
        captured["body"] = body
        return {}

    monkeypatch.setattr(pr_streak, "_token", lambda: "fake")
    monkeypatch.setattr(pr_streak, "_github_env", lambda: ("https://u", "r"))
    monkeypatch.setattr(pr_streak, "_read_pr_comments", lambda *_: [])
    monkeypatch.setattr(pr_streak, "_current_head_sha", lambda: "deadbeef")
    monkeypatch.setattr(github_client, "http_request", fake_request)
    rc = pr_streak.cmd_set(1, 2)
    assert rc == 0
    assert captured["body"] is not None
    body_str: str = captured["body"]["body"]
    assert "head: deadbeef" in body_str
    assert "streak: 2" in body_str


def test_cmd_set_updates_existing_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        url: str,
        _token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> dict[str, Any]:
        captured["method"] = method
        captured["url"] = url
        captured["body"] = body
        return {}

    monkeypatch.setattr(pr_streak, "_token", lambda: "fake")
    monkeypatch.setattr(pr_streak, "_github_env", lambda: ("https://u", "r"))
    monkeypatch.setattr(
        pr_streak,
        "_read_pr_comments",
        lambda *_: [{"id": 99, "body": "<!-- ai-review-streak -->\nstreak: 1"}],
    )
    monkeypatch.setattr(pr_streak, "_current_head_sha", lambda: "")
    monkeypatch.setattr(github_client, "http_request", fake_request)
    rc = pr_streak.cmd_set(1, 2)
    assert rc == 0
    assert captured["method"] == "PATCH"
    assert "comments/99" in captured["url"]


def test_cmd_set_no_token_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pr_streak, "_token", lambda: "")
    assert pr_streak.cmd_set(1, 0) == 1


def test_cmd_set_includes_review_field(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_request(
        method: str,
        url: str,
        _token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> dict[str, Any]:
        captured["body"] = body
        return {}

    monkeypatch.setattr(pr_streak, "_token", lambda: "fake")
    monkeypatch.setattr(pr_streak, "_github_env", lambda: ("https://u", "r"))
    monkeypatch.setattr(pr_streak, "_read_pr_comments", lambda *_: [])
    monkeypatch.setattr(pr_streak, "_current_head_sha", lambda: "")
    monkeypatch.setattr(github_client, "http_request", fake_request)
    rc = pr_streak.cmd_set(1, 2, comment_texts=["バグが残っています\n詳細"])
    assert rc == 0
    assert captured["body"] is not None
    assert "review: " in captured["body"]["body"]


def test_find_streak_comment_roundtrips_review_texts() -> None:
    encoded = pr_streak._encode_review_texts(["バグが残っています\n詳細"])
    comments = [
        {
            "id": 5,
            "body": f"<!-- ai-review-streak -->\nstreak: 1\nreview: {encoded}",
        },
    ]
    result = find_streak_comment(comments)
    assert result is not None
    assert result[3] == ["バグが残っています\n詳細"]


def test_find_streak_comment_empty_review_when_missing() -> None:
    comments = [
        {"id": 5, "body": "<!-- ai-review-streak -->\nstreak: 1"},
    ]
    result = find_streak_comment(comments)
    assert result is not None
    assert not result[3]


def test_cmd_evaluate_stale_blocking_demoted_to_low(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Issue #55 B2: 前回レビューと同一のコメントは MIDDLE でも LOW に降格して
    # streak を進める (escape 条件は変更しない)。Issue #67 以降 comment_text は
    # path/line/title のアンカー形式で保存されるため、prev も同じ形式で与える。
    from ame_ai_review_system import stale_detect

    prev_text = stale_detect.comment_text(
        {
            "severity": "MIDDLE",
            "path": "a",
            "line": 1,
            "title": "バグが残っています",
            "body": "バグが残っています の詳細",
        },
    )
    encoded = pr_streak._encode_review_texts([prev_text])
    monkeypatch.setattr(pr_streak, "_token", lambda: "fake")
    monkeypatch.setattr(pr_streak, "_github_env", lambda: ("https://u", "r"))
    monkeypatch.setattr(
        pr_streak,
        "_read_pr_comments",
        lambda *_: [
            {
                "id": 1,
                "body": f"<!-- ai-review-streak -->\nstreak: 0\nreview: {encoded}",
            },
        ],
    )
    monkeypatch.setattr(pr_streak, "cmd_set", lambda *_a, **_kw: 0)
    review_path = _write_review(
        tmp_path,
        {
            "summary": "same issue",
            "comments": [
                {
                    "severity": "MIDDLE",
                    "path": "a",
                    "line": 1,
                    "title": "バグが残っています",
                    "body": "バグが残っています の詳細",
                },
            ],
        },
    )
    rc = pr_streak.cmd_evaluate(1, review_path)
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["streak"] == 1
    assert out["allow"] is False


# ---------------------------
# main (argument parsing)
# ---------------------------


def test_main_no_args_returns_2() -> None:
    assert pr_streak.main(["prog"]) == 2


def test_main_invalid_pr_number_returns_2() -> None:
    assert pr_streak.main(["prog", "get", "notanumber"]) == 2


def test_main_unknown_command_returns_2() -> None:
    assert pr_streak.main(["prog", "bogus", "1"]) == 2


def test_main_set_requires_streak_arg() -> None:
    assert pr_streak.main(["prog", "set", "1"]) == 2


def test_main_evaluate_requires_path_arg() -> None:
    assert pr_streak.main(["prog", "evaluate", "1"]) == 2


# ---------------------------
# _token (file fallback)
# ---------------------------


def test_token_reads_from_file(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = Path("/fake/home")
    monkeypatch.setattr(pathlib.Path, "home", lambda: fake_home)
    monkeypatch.setattr(Path, "exists", lambda _self: True)
    monkeypatch.setattr(Path, "is_file", lambda _self: True)
    monkeypatch.setattr(Path, "read_text", lambda _self, **_kw: "secrettoken")
    monkeypatch.setattr(os, "environ", {})
    assert token() == "secrettoken"


def test_token_fallback_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "environ", {"GITHUB_PAT_TOKEN": "envtoken"})
    monkeypatch.setattr(Path, "exists", lambda _self: False)
    monkeypatch.setattr(Path, "is_file", lambda _self: False)
    assert token() == "envtoken"
