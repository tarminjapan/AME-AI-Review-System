# pyright: basic
from __future__ import annotations

import argparse
from typing import Any

import pytest
from ame_ai_review_system import github_client, main, review_config
from ame_ai_review_system.main import (
    LIMIT_NOTICE_MARKER,
    SKIP_NOTICE_MARKER,
    skip_notice_already_posted,
)

_MARKER = f"{SKIP_NOTICE_MARKER}-pr38"
_ISSUE_URL = "https://api.github.com/repos/AME-Team/AME-AI-Review-System/issues/38"


# --- _reviewer_author_login (Issue #55 B5) -----------------------------------


def test_reviewer_author_login_resolves_via_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        github_client,
        "http_request",
        lambda _method, _url, _token: {"login": "developer"},
    )
    assert (
        main._reviewer_author_login("https://api.github.com", "tok", "ame-ai-reviewer")
        == "developer"
    )


def test_reviewer_author_login_falls_back_to_bot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(*_a: Any, **_kw: Any) -> Any:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(github_client, "http_request", _raise)
    assert (
        main._reviewer_author_login("https://api.github.com", "tok", "ame-ai-reviewer")
        == "ame-ai-reviewer[bot]"
    )


def test_reviewer_author_login_non_dict_falls_back_to_bot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        github_client,
        "http_request",
        lambda _method, _url, _token: ["not", "a", "dict"],
    )
    assert (
        main._reviewer_author_login("https://api.github.com", "tok", "ame-ai-reviewer")
        == "ame-ai-reviewer[bot]"
    )


def test_skip_notice_already_posted_false_when_absent() -> None:
    comments = [{"body": "hello", "issue_url": _ISSUE_URL}]
    assert not skip_notice_already_posted(comments, _MARKER, _ISSUE_URL)


def test_skip_notice_already_posted_true_when_present() -> None:
    comments = [
        {"body": f"<!-- {_MARKER} -->", "issue_url": _ISSUE_URL},
    ]
    assert skip_notice_already_posted(comments, _MARKER, _ISSUE_URL)


def test_skip_notice_already_posted_ignores_other_prs() -> None:
    other_url = "https://api.github.com/repos/AME-Team/AME-AI-Review-System/issues/1"
    comments = [
        {"body": f"<!-- {_MARKER} -->", "issue_url": other_url},
    ]
    assert not skip_notice_already_posted(comments, _MARKER, _ISSUE_URL)


def test_skip_notice_already_posted_tolerates_trailing_slash() -> None:
    comments = [
        {"body": f"<!-- {_MARKER} -->", "issue_url": _ISSUE_URL + "/"},
    ]
    assert skip_notice_already_posted(comments, _MARKER, _ISSUE_URL)


def test_skip_notice_already_posted_ignores_missing_fields() -> None:
    assert not skip_notice_already_posted([{}], _MARKER, _ISSUE_URL)


# --- engine info injection sentinel (Issue #40) -----------------------------


def test_run_engine_capture_injects_show_info_by_default(
    capture_engine_env: dict[str, Any],
) -> None:
    # 哨戒テスト: 既定では Gate2 の表示フラグを必ず子プロセスへ注入する (Issue #40)。
    main._run_engine_capture({}, "PROMPT")
    assert capture_engine_env["env"].get("AME_ENGINE_SHOW_INFO") == "1"


def test_run_engine_capture_omits_show_info_when_false(
    capture_engine_env: dict[str, Any],
) -> None:
    main._run_engine_capture({}, "PROMPT", show_info=False)
    assert capture_engine_env["env"].get("AME_ENGINE_SHOW_INFO") == "0"


# --- _run_engine_capture timeout propagation (Issue #94) ---------------------


def test_run_engine_capture_forwards_timeout(
    capture_engine_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 哨戒テスト: REVIEW_TIMEOUT_SECONDS が親 subprocess の timeout に反映される (Issue #94)。
    # conftest が subprocess.run を monkeypatch しているため timeout 引数を捕捉できる。
    monkeypatch.setenv("REVIEW_TIMEOUT_SECONDS", "1234.5")
    main._run_engine_capture({"timeout": 999.0}, "PROMPT")
    assert capture_engine_env["timeout"] == pytest.approx(1234.5)


def test_run_engine_capture_default_timeout(
    capture_engine_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # REVIEW_TIMEOUT_SECONDS 未設定時は既定 600 が使われる。
    monkeypatch.delenv("REVIEW_TIMEOUT_SECONDS", raising=False)
    main._run_engine_capture({}, "PROMPT")
    assert capture_engine_env["timeout"] == pytest.approx(600.0)


# --- _run_git_check (Issue #95) ----------------------------------------------


def test_run_git_check_success(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_run(
        args: list[str],
        **kwargs: Any,
    ) -> Any:
        captured["args"] = args
        captured["kwargs"] = kwargs

        class _Result:
            returncode = 0
            stdout = "stdout-data"
            stderr = ""

        return _Result()

    monkeypatch.setattr("subprocess.run", _fake_run)
    ok, detail = main._run_git_check(["rev-parse", "HEAD"])
    assert ok is True
    assert detail == "stdout-data"


def test_run_git_check_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_run(args: list[str], **kwargs: Any) -> Any:
        class _Result:
            returncode = 128
            stdout = ""
            stderr = "fatal: not a git repository"

        return _Result()

    monkeypatch.setattr("subprocess.run", _fake_run)
    ok, detail = main._run_git_check(["checkout", "nope"])
    assert ok is False
    assert "fatal" in detail


def test_run_git_check_spawn_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_run(args: list[str], **kwargs: Any) -> Any:
        message = "git not found"
        raise FileNotFoundError(message)

    monkeypatch.setattr("subprocess.run", _fake_run)
    ok, detail = main._run_git_check(["rev-parse", "HEAD"])
    assert ok is False
    assert "git not found" in detail


def test_run_git_check_default_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    # 既定は _run_git と同じ 30 秒。fetch のみ呼び出し側で _git_timeout() を明示する。
    captured: dict[str, Any] = {}

    def _fake_run(args: list[str], **kwargs: Any) -> Any:
        captured["timeout"] = kwargs.get("timeout")

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Result()

    monkeypatch.setattr("subprocess.run", _fake_run)
    monkeypatch.delenv("GIT_TIMEOUT_SECONDS", raising=False)
    ok, _detail = main._run_git_check(["rev-parse", "HEAD"])
    assert ok is True
    assert captured["timeout"] == pytest.approx(30.0)


def test_run_git_check_explicit_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    # fetch は _git_timeout() (既定 300) を明示して呼ぶ。
    captured: dict[str, Any] = {}

    def _fake_run(args: list[str], **kwargs: Any) -> Any:
        captured["timeout"] = kwargs.get("timeout")

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Result()

    monkeypatch.setattr("subprocess.run", _fake_run)
    monkeypatch.delenv("GIT_TIMEOUT_SECONDS", raising=False)
    ok, _detail = main._run_git_check(
        ["fetch", "origin", "main"], timeout=main._git_timeout()
    )
    assert ok is True
    assert captured["timeout"] == pytest.approx(300.0)


def test_git_timeout_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_TIMEOUT_SECONDS", "120")
    assert main._git_timeout() == pytest.approx(120.0)


def test_git_timeout_fallback_on_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_TIMEOUT_SECONDS", "abc")
    assert main._git_timeout() == pytest.approx(300.0)


def test_git_timeout_fallback_on_inf(monkeypatch: pytest.MonkeyPatch) -> None:
    # Gate 1 指摘対応: inf / nan は既定 300 へフォールバックする。
    monkeypatch.setenv("GIT_TIMEOUT_SECONDS", "inf")
    assert main._git_timeout() == pytest.approx(300.0)
    monkeypatch.setenv("GIT_TIMEOUT_SECONDS", "nan")
    assert main._git_timeout() == pytest.approx(300.0)


def test_git_ref_check_rejects_invalid_ref_without_spawn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 不正 refname は検証段階で弾き、subprocess を起動しない (Gate 1 指摘対応)。
    spawned: list[list[str]] = []

    def _fake_run(args: list[str], **kwargs: Any) -> Any:
        spawned.append(args)

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Result()

    monkeypatch.setattr("subprocess.run", _fake_run)
    ok, detail = main._git_ref_check("checkout", "bad..name")
    assert ok is False
    assert "invalid refname" in detail
    assert spawned == []


def test_git_ref_check_runs_valid_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    # 有効な refname はリスト引数で git へ渡る (検証済み ref から args を内部生成)。
    spawned: list[list[str]] = []

    def _fake_run(args: list[str], **kwargs: Any) -> Any:
        spawned.append(args)

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Result()

    monkeypatch.setattr("subprocess.run", _fake_run)
    ok, _detail = main._git_ref_check("checkout", "feature/foo")
    assert ok is True
    assert spawned == [["git", "checkout", "feature/foo"]]


def test_git_ref_check_builds_fetch_args_from_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # fetch は extra_args と検証済み ref から args を組み立てる。
    spawned: list[list[str]] = []

    def _fake_run(args: list[str], **kwargs: Any) -> Any:
        spawned.append(args)

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Result()

    monkeypatch.setattr("subprocess.run", _fake_run)
    ok, _detail = main._git_ref_check("fetch", "feature/foo", extra_args=["origin"])
    assert ok is True
    assert spawned == [["git", "fetch", "origin", "feature/foo"]]


# --- _is_valid_ref_name (Issue #95) ------------------------------------------


def test_is_valid_ref_name_accepts_git_refs() -> None:
    # git の refname 規約で有効なブランチ名 (@ # + ( ) % , { } ; $ 等) を許可する。
    for name in [
        "main",
        "feature/foo",
        "hotfix#123",
        "release@1.0",
        "feature/foo+bar",
        "bug/fix-123",
        "fix(issue)",
        "feat(parser)%",
        "fix/issue,42",
        "fix{scoped}",
        "fix;scoped",
        "fix$name",
    ]:
        assert main._is_valid_ref_name(name), name


def test_is_valid_ref_name_rejects_unsafe() -> None:
    for name in [
        "",
        "@",
        "-foo",
        "--orphan=x",
        ".foo",
        "/foo",
        "foo bar",
        "foo\tbar",
        "foo..bar",
        "foo//bar",
        "foo\\bar",
        "foo/",
        "foo.lock",
        "feature/foo.lock",
        "feature/.bar",
        "foo@{bar",
        "foo~bar",
        "foo^bar",
        "foo:bar",
        "foo?bar",
        "foo*bar",
        "foo[bar",
        "foo\x00bar",
    ]:
        assert not main._is_valid_ref_name(name), name


# --- _post_limit_notice / pr_max_reviews (Issue #129) ------------------------


def test_post_limit_notice_posts_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []

    def _fake_http(method: str, url: str, _token: str, **_kw: Any) -> Any:
        if method == "POST":
            posts.append(url)
        return []

    monkeypatch.setattr(github_client, "http_request", _fake_http)
    main._post_limit_notice(
        "https://api.github.com",
        "AME-Team/AME-AI-Review-System",
        38,
        "tok",
        3,
    )
    assert len(posts) == 1
    assert "issues/38/comments" in posts[0]


def test_post_limit_notice_dedups_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # マーカー付き通知が既にある場合は二重投稿しない (skip_notice と同パターン)。
    marker = f"{LIMIT_NOTICE_MARKER}-pr38"
    issue_url = "https://api.github.com/repos/AME-Team/AME-AI-Review-System/issues/38"
    posts: list[str] = []

    def _fake_http(method: str, url: str, _token: str, **_kw: Any) -> Any:
        if method == "GET":
            return [{"body": f"<!-- {marker} -->", "issue_url": issue_url}]
        if method == "POST":
            posts.append(url)
        return []

    monkeypatch.setattr(github_client, "http_request", _fake_http)
    main._post_limit_notice(
        "https://api.github.com",
        "AME-Team/AME-AI-Review-System",
        38,
        "tok",
        3,
    )
    assert posts == []


def test_cmd_review_skips_at_pr_max_reviews(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Issue #129: 総レビュー回数 (pr_max_reviews) 到達時はレビューせずスキップし、
    # PR へ上限到達通知を投稿する。
    monkeypatch.setenv("GITHUB_REPOSITORY", "AME-Team/AME-AI-Review-System")
    monkeypatch.setenv("GITHUB_API_URL", "https://api.github.com")
    reviewed = [
        {
            "user": {"login": "ame-ai-reviewer[bot]"},
            "body": f"<!-- reviewed-sha: {'b' * 40} -->",
        },
        {
            "user": {"login": "ame-ai-reviewer[bot]"},
            "body": f"<!-- reviewed-sha: {'c' * 40} -->",
        },
        {
            "user": {"login": "ame-ai-reviewer[bot]"},
            "body": f"<!-- reviewed-sha: {'d' * 40} -->",
        },
    ]
    calls: list[tuple[str, str, str]] = []

    def _fake_http(method: str, url: str, _token: str, **_kw: Any) -> Any:
        body = str(_kw.get("body", {}).get("body", ""))
        calls.append((method, url, body))
        # 上限通知の重複確認用 GET は既存コメント無しで返す。
        if method == "GET" and "/issues/comments" in url:
            return []
        return reviewed

    monkeypatch.setattr(github_client, "http_request", _fake_http)
    monkeypatch.setattr(main, "_run_git", lambda *_a: "a" * 40)
    monkeypatch.setattr(
        "ame_ai_review_system.pr_streak.cmd_check",
        lambda *_a: 1,
    )
    fake_token = "tok"
    args = argparse.Namespace(
        pr_number=38,
        base_ref="main",
        pr_title="",
        pr_body="",
        prompt_file=None,
        token=fake_token,
    )
    assert main.cmd_review(args) == 0
    out = capsys.readouterr().out
    assert "(max 3)" in out
    assert any(
        method == "POST" and LIMIT_NOTICE_MARKER in body for method, url, body in calls
    )


# --- external CI gate (Issue #140) -------------------------------------------


def test_post_external_ci_notice_posts_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    posts: list[str] = []

    def _fake_http(method: str, url: str, _token: str, **_kw: Any) -> Any:
        if method == "POST":
            posts.append(url)
        return []

    monkeypatch.setattr(github_client, "http_request", _fake_http)
    main._post_external_ci_notice(
        "https://api.github.com",
        "AME-Team/AME-AI-Review-System",
        38,
        "tok",
        ["typegen-check"],
    )
    assert len(posts) == 1
    assert "issues/38/comments" in posts[0]


def test_post_external_ci_notice_dedups_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # マーカー付き通知が既にある場合は二重投稿しない (skip_notice と同パターン)。
    marker = f"{main.EXTERNAL_CI_NOTICE_MARKER}-pr38"
    issue_url = "https://api.github.com/repos/AME-Team/AME-AI-Review-System/issues/38"
    posts: list[str] = []

    def _fake_http(method: str, url: str, _token: str, **_kw: Any) -> Any:
        if method == "GET":
            return [{"body": f"<!-- {marker} -->", "issue_url": issue_url}]
        if method == "POST":
            posts.append(url)
        return []

    monkeypatch.setattr(github_client, "http_request", _fake_http)
    main._post_external_ci_notice(
        "https://api.github.com",
        "AME-Team/AME-AI-Review-System",
        38,
        "tok",
        ["typegen-check"],
    )
    assert posts == []


def test_cmd_review_skips_on_external_ci_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Issue #140: 外部 CI が失敗中の HEAD SHA では AI レビューをスキップし通知する。
    import subprocess

    monkeypatch.setenv("GITHUB_REPOSITORY", "AME-Team/AME-AI-Review-System")
    monkeypatch.setenv("GITHUB_API_URL", "https://api.github.com")
    sha = "a" * 40
    posts: list[str] = []

    def _fake_http(method: str, url: str, _token: str, **_kw: Any) -> Any:
        if method == "POST":
            posts.append(url)
        return []  # reviews も comment 既存確認も空

    def _fake_run_git(args: list[str], **kwargs: Any) -> str:
        if args[:2] == ["rev-parse", "HEAD"]:
            return sha
        if args[:1] == ["diff"] and len(args) > 1 and args[1].startswith("origin/"):
            return (
                "diff --git a/x.py b/x.py\n"
                "index 0000000..1111111 100644\n"
                "--- a/x.py\n"
                "+++ b/x.py\n"
                "@@ -0,0 +1 @@\n"
                "+print('hi')\n"
            )
        if args[:2] == ["diff", "--name-only"]:
            return "x.py"
        if args[:1] == ["log"]:
            return "deadbeef fix"
        return ""

    monkeypatch.setattr(review_config, "pr_review_require_external_ci", lambda _c: True)
    monkeypatch.setattr(
        github_client,
        "list_commit_check_runs",
        lambda *_a, **_kw: [
            {"name": "typegen-check", "conclusion": "failure", "status": "completed"}
        ],
    )
    monkeypatch.setattr(github_client, "http_request", _fake_http)
    monkeypatch.setattr(main, "_run_git", _fake_run_git)
    monkeypatch.setattr("ame_ai_review_system.pr_streak.cmd_check", lambda *_a: 1)
    # 静的解析 precheck を成功扱いにする。
    monkeypatch.setattr(
        subprocess, "run", lambda *_a, **_kw: type("R", (), {"returncode": 0})()
    )

    fake_token = "tok"
    args = argparse.Namespace(
        pr_number=38,
        base_ref="main",
        pr_title="",
        pr_body="",
        prompt_file=None,
        token=fake_token,
    )
    assert main.cmd_review(args) == 0
    out = capsys.readouterr().out
    assert "skipping AI review" in out
    assert any("issues/38/comments" in u for u in posts)
