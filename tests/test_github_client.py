"""Unit tests for the shared GitHub REST/GraphQL client module."""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Any

import pytest
from ame_ai_review_system import github_client

# ============================================================================
# resolve_env
# ============================================================================


def test_resolve_env_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_API_URL", "https://api.github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "AME-Team/AME-AI-Review-System")
    api_url, repo = github_client.resolve_env()
    assert api_url == "https://api.github.com"
    assert repo == "AME-Team/AME-AI-Review-System"


def test_resolve_env_missing_repo_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    with pytest.raises(RuntimeError, match="GITHUB_REPOSITORY"):
        github_client.resolve_env()


def test_resolve_env_custom_api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_API_URL", "https://github.enterprise/api/v3")
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
    api_url, _ = github_client.resolve_env()
    assert api_url == "https://github.enterprise/api/v3"


# ============================================================================
# get_token
# ============================================================================


def test_get_token_from_file(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    token_file = tmp_path / "github.token"
    token_file.write_text("filetoken123", encoding="utf-8")
    monkeypatch.delenv("GITHUB_PAT_TOKEN", raising=False)
    assert github_client.get_token(str(token_file)) == "filetoken123"


def test_get_token_fallback_to_env(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token_file = tmp_path / "missing.token"
    monkeypatch.setenv("GITHUB_PAT_TOKEN", "envtoken456")
    assert github_client.get_token(str(token_file)) == "envtoken456"


def test_get_token_custom_env_key(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token_file = tmp_path / "missing.token"
    monkeypatch.delenv("GITHUB_PAT_TOKEN", raising=False)
    monkeypatch.setenv("REVIEWER_BOT_TOKEN", "customtoken789")
    assert (
        github_client.get_token(str(token_file), env_key="REVIEWER_BOT_TOKEN")
        == "customtoken789"
    )


def test_get_token_missing_raises(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token_file = tmp_path / "missing.token"
    monkeypatch.delenv("GITHUB_PAT_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="GitHub token not found"):
        github_client.get_token(str(token_file))


# ============================================================================
# bot_login
# ============================================================================


def test_bot_login_appends_bot_suffix() -> None:
    """App slug に [bot] サフィックスが付与されることを検証する。."""
    assert github_client.bot_login("ame-ai-reviewer") == "ame-ai-reviewer[bot]"


def test_bot_login_idempotent_for_already_bot_login() -> None:
    """すでに [bot] 付きの名前はそのまま返すことを検証する。."""
    assert github_client.bot_login("ame-ai-reviewer[bot]") == "ame-ai-reviewer[bot]"


def test_bot_login_preserves_hyphenated_slug() -> None:
    """ハイフン入り slug も正しく処理されることを検証する。."""
    assert github_client.bot_login("security-reviewer") == "security-reviewer[bot]"


# ============================================================================
# reviewer_logins (Issue #92)
# ============================================================================


def test_reviewer_logins_resolves_real_login(monkeypatch: pytest.MonkeyPatch) -> None:
    """PAT 運用で GET /user が実投稿者を返す場合、和集合に含まれることを検証する。."""

    def fake_http_request(
        method: str,
        url: str,
        token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> dict[str, str]:
        return {"login": "developer"}

    monkeypatch.setattr(github_client, "http_request", fake_http_request)
    assert github_client.reviewer_logins(
        "https://api.github.com", "tok-real", "ame-ai-reviewer"
    ) == {"developer", "ame-ai-reviewer[bot]"}


def test_reviewer_logins_falls_back_to_bot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /user 失敗時は App 運用の後方互換として [bot] のみ返すことを検証する。."""

    def _raise(
        method: str,
        url: str,
        token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> dict[str, Any]:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(github_client, "http_request", _raise)
    assert github_client.reviewer_logins(
        "https://api.github.com", "tok-bot", "ame-ai-reviewer"
    ) == {"ame-ai-reviewer[bot]"}


def test_reviewer_logins_non_dict_response_falls_back_to_bot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /user が非 dict を返した場合は [bot] のみ返すことを検証する。."""

    def fake_http_request(
        method: str,
        url: str,
        token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> list[str]:
        return ["not", "a", "dict"]

    monkeypatch.setattr(github_client, "http_request", fake_http_request)
    assert github_client.reviewer_logins(
        "https://api.github.com", "tok-nondict", "ame-ai-reviewer"
    ) == {"ame-ai-reviewer[bot]"}


def test_reviewer_logins_failure_not_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r"""GET /user の失敗結果はキャッシュせず、後続呼び出しで再解決できることを検証する.

    lru_cache だと一時的な API 失敗がプロセス内で固定され、PAT 運用の実投稿者 login が
    解決されず Issue #92 が再発するため、成功時のみキャッシュする手動実装を採用した
    (Gate 1 指摘対応)。
    """
    calls: list[str] = []

    def _fail(
        method: str,
        url: str,
        token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> dict[str, Any]:
        calls.append(url)
        msg = "temporary 5xx"
        raise RuntimeError(msg)

    monkeypatch.setattr(github_client, "http_request", _fail)
    first = github_client.reviewer_logins(
        "https://api.github.com", "tok-fail", "ame-ai-reviewer"
    )
    second = github_client.reviewer_logins(
        "https://api.github.com", "tok-fail", "ame-ai-reviewer"
    )
    assert first == {"ame-ai-reviewer[bot]"}
    assert second == {"ame-ai-reviewer[bot]"}
    # 失敗はキャッシュされないため、2 回目の呼び出しでも API へ再アクセスする。
    assert len(calls) == 2


def test_reviewer_logins_success_is_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /user の成功結果はキャッシュされ、繰り返し呼び出しても API を 1 回しか叩かない。."""
    calls: list[str] = []

    def _ok(
        method: str,
        url: str,
        token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> dict[str, str]:
        calls.append(url)
        return {"login": "developer"}

    monkeypatch.setattr(github_client, "http_request", _ok)
    first = github_client.reviewer_logins(
        "https://api.github.com", "tok-cache-ok", "ame-ai-reviewer"
    )
    second = github_client.reviewer_logins(
        "https://api.github.com", "tok-cache-ok", "ame-ai-reviewer"
    )
    assert first == {"developer", "ame-ai-reviewer[bot]"}
    assert second == {"developer", "ame-ai-reviewer[bot]"}
    assert len(calls) == 1


def test_reviewer_logins_auth_error_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """恒久的不許可 (401、App トークンの GET /user) はキャッシュし再アクセスしない.

    App 運用では ``GET /user`` が毎回 401 になるため、プロセス毎の無駄な API 呼び出しと
    エラーログノイズを避ける (Gate 2 指摘対応)。
    """
    calls: list[str] = []

    def _unauthorized(
        method: str,
        url: str,
        token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> dict[str, Any]:
        calls.append(url)
        raise github_client.HttpError(401, "Unauthorized")

    monkeypatch.setattr(github_client, "http_request", _unauthorized)
    first = github_client.reviewer_logins(
        "https://api.github.com", "tok-401", "ame-ai-reviewer"
    )
    second = github_client.reviewer_logins(
        "https://api.github.com", "tok-401", "ame-ai-reviewer"
    )
    assert first == {"ame-ai-reviewer[bot]"}
    assert second == {"ame-ai-reviewer[bot]"}
    assert len(calls) == 1


def test_reviewer_logins_401_emits_warning_once(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """401 恒久キャッシュ時に警告を一度だけ出力する (Gate 1 指摘対応)."""

    def _unauthorized(
        method: str,
        url: str,
        token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> dict[str, Any]:
        raise github_client.HttpError(401, "Unauthorized")

    monkeypatch.setattr(github_client, "http_request", _unauthorized)
    github_client.reviewer_logins(
        "https://api.github.com", "tok-warn", "ame-ai-reviewer"
    )
    github_client.reviewer_logins(
        "https://api.github.com", "tok-warn", "ame-ai-reviewer"
    )
    captured = capsys.readouterr()
    assert "401" in captured.err
    assert "WARNING" in captured.err
    # キャッシュ後の 2 回目は API を叩かないため警告も出ない (1 回のみ)。
    assert captured.err.count("WARNING") == 1


def test_reviewer_logins_rate_limit_403_not_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """レート制限 403 はキャッシュせず再解決できることを検証する.

    403 はレート制限超過を伴い得る (X-RateLimit-Remaining: 0)。一律キャッシュすると
    一時障害で ``[bot]`` 固定照合へ退行し Issue #92 が再発するため対象外とする
    (Gate 1 指摘対応)。
    """
    calls: list[str] = []

    def _rate_limited(
        method: str,
        url: str,
        token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> dict[str, Any]:
        calls.append(url)
        raise github_client.HttpError(403, "API rate limit exceeded")

    monkeypatch.setattr(github_client, "http_request", _rate_limited)
    first = github_client.reviewer_logins(
        "https://api.github.com", "tok-403", "ame-ai-reviewer"
    )
    second = github_client.reviewer_logins(
        "https://api.github.com", "tok-403", "ame-ai-reviewer"
    )
    assert first == {"ame-ai-reviewer[bot]"}
    assert second == {"ame-ai-reviewer[bot]"}
    assert len(calls) == 2


def test_reviewer_logins_5xx_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """一時障害 (5xx) はキャッシュせず、後続呼び出しで再解決できることを検証する。."""
    calls: list[str] = []

    def _server_error(
        method: str,
        url: str,
        token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> dict[str, Any]:
        calls.append(url)
        raise github_client.HttpError(503, "Service Unavailable")

    monkeypatch.setattr(github_client, "http_request", _server_error)
    first = github_client.reviewer_logins(
        "https://api.github.com", "tok-5xx", "ame-ai-reviewer"
    )
    second = github_client.reviewer_logins(
        "https://api.github.com", "tok-5xx", "ame-ai-reviewer"
    )
    assert first == {"ame-ai-reviewer[bot]"}
    assert second == {"ame-ai-reviewer[bot]"}
    assert len(calls) == 2


# ============================================================================
# mentions_reviewer
# ============================================================================


def test_mentions_reviewer_detects_short_form() -> None:
    """@ame-ai-reviewer (旧PAT形式) を検出することを検証する。."""
    assert github_client.mentions_reviewer(
        "@ame-ai-reviewer 修正しました", "ame-ai-reviewer"
    )


def test_mentions_reviewer_detects_bot_form() -> None:
    """@ame-ai-reviewer[bot] (App公式形式) を検出することを検証する。."""
    assert github_client.mentions_reviewer(
        "@ame-ai-reviewer[bot] 修正しました", "ame-ai-reviewer"
    )


def test_mentions_reviewer_negative_no_mention() -> None:
    """メンションがない本文は False となることを検証する。."""
    assert not github_client.mentions_reviewer(
        "修正しました。LGTM お願いします。", "ame-ai-reviewer"
    )


def test_mentions_reviewer_negative_different_user() -> None:
    """別ユーザーへのメンションは False となることを検証する。."""
    assert not github_client.mentions_reviewer(
        "@other-reviewer 修正しました", "ame-ai-reviewer"
    )


def test_mentions_reviewer_substring_safety() -> None:
    """Bot 形式の明確な境界ケースを検証する。.

    本実装では部分一致検出のため、``@ame-ai-reviewer[bot]`` の直後に
    句読点が続くケースも True になることを確認する。
    """
    assert github_client.mentions_reviewer(
        "@ame-ai-reviewer[bot], 修正しました", "ame-ai-reviewer"
    )


# ============================================================================
# http_request
# ============================================================================


class _FakeResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> Any:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_http_request_sets_bearer_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(req: urllib.request.Request) -> _FakeResponse:
        captured["url"] = req.full_url
        captured["method"] = req.method
        captured["headers"] = {k: req.headers[k] for k in req.headers}
        captured["data"] = req.data
        return _FakeResponse(b'{"ok": true}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = github_client.http_request(
        "GET",
        "https://api.github.com/repos/o/r/pulls/1",
        "tok_ABC",
    )
    assert result == {"ok": True}
    assert captured["method"] == "GET"
    assert captured["headers"]["Authorization"] == "Bearer tok_ABC"
    assert captured["headers"]["Accept"] == "application/vnd.github+json"
    assert captured["headers"]["X-github-api-version"] == "2022-11-28"
    assert captured["data"] is None


def test_http_request_post_with_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(req: urllib.request.Request) -> _FakeResponse:
        captured["method"] = req.method
        captured["data"] = req.data
        captured["headers"] = {k: req.headers[k] for k in req.headers}
        return _FakeResponse(b'{"id": 42}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = github_client.http_request(
        "POST",
        "https://api.github.com/repos/o/r/pulls/1/comments",
        "tok_X",
        body={"body": "hello"},
    )
    assert result == {"id": 42}
    assert captured["method"] == "POST"
    assert captured["headers"]["Content-type"] == "application/json"
    assert captured["data"] == b'{"body": "hello"}'


def test_http_request_http_error_raises_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from email.message import Message

    def fake_urlopen(_req: urllib.request.Request) -> _FakeResponse:
        raise urllib.error.HTTPError(
            url="https://api.github.com/x",
            code=422,
            msg="Unprocessable",
            hdrs=Message(),
            fp=None,
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="GitHub API error 422"):
        github_client.http_request("GET", "https://api.github.com/x", "tok")


def test_http_request_diff_accept_returns_raw_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(_req: urllib.request.Request) -> _FakeResponse:
        return _FakeResponse(b"diff --git a/x b/x\n+hello\n")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = github_client.http_request(
        "GET",
        "https://api.github.com/repos/o/r/pulls/1",
        "tok",
        accept="application/vnd.github.diff",
    )
    assert result == "diff --git a/x b/x\n+hello\n"


def test_http_request_empty_body_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(_req: urllib.request.Request) -> _FakeResponse:
        return _FakeResponse(b"")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert (
        github_client.http_request("DELETE", "https://api.github.com/x", "tok") is None
    )


# ============================================================================
# graphql_request
# ============================================================================


def test_graphql_request_success(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_http_request(
        method: str,
        url: str,
        token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> dict[str, Any]:
        captured["method"] = method
        captured["url"] = url
        captured["body"] = body
        return {"data": {"viewer": {"login": "octocat"}}}

    monkeypatch.setattr(github_client, "http_request", fake_http_request)
    result = github_client.graphql_request(
        "query { viewer { login } }",
        {},
        "tok_G",
    )
    assert result == {"viewer": {"login": "octocat"}}
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.github.com/graphql"
    assert captured["body"]["query"] == "query { viewer { login } }"


def test_graphql_request_http200_with_errors_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 200 応答でも GraphQL レベルの errors 配列を持つ場合を検出する."""

    def fake_http_request(
        _method: str,
        _url: str,
        _token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> dict[str, Any]:
        assert body is not None
        return {
            "data": None,
            "errors": [
                {
                    "type": "FORBIDDEN",
                    "message": "Resource not accessible by integration",
                },
            ],
        }

    monkeypatch.setattr(github_client, "http_request", fake_http_request)
    with pytest.raises(RuntimeError, match="GraphQL errors"):
        github_client.graphql_request("query { x }", {}, "tok")


def test_graphql_request_no_data_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_http_request(
        _method: str,
        _url: str,
        _token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> dict[str, Any]:
        return {"neither": "data nor errors"}

    monkeypatch.setattr(github_client, "http_request", fake_http_request)
    with pytest.raises(TypeError, match="no data"):
        github_client.graphql_request("query { x }", {}, "tok")


def test_graphql_request_non_dict_response_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_http_request(
        _method: str,
        _url: str,
        _token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> Any:
        return ["unexpected", "list"]

    monkeypatch.setattr(github_client, "http_request", fake_http_request)
    with pytest.raises(TypeError, match="Unexpected GraphQL response"):
        github_client.graphql_request("query { x }", {}, "tok")


# ============================================================================
# list_review_threads / resolve_review_thread
# ============================================================================


def test_list_review_threads_paginates_and_flattens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    calls: list[dict[str, Any]] = []

    def fake_graphql(
        query: str,
        variables: dict[str, Any],
        token: str,
    ) -> dict[str, Any]:
        calls.append({"query": query, "variables": variables})
        after = variables["after"]
        if after is None:
            return {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": True, "endCursor": "cursor1"},
                            "nodes": [
                                {
                                    "id": "T1",
                                    "isResolved": False,
                                    "comments": {"nodes": [{"databaseId": 100}]},
                                },
                            ],
                        },
                    },
                },
            }
        return {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {
                                "id": "T2",
                                "isResolved": True,
                                "comments": {
                                    "nodes": [{"databaseId": 200}, {"databaseId": 201}]
                                },
                            },
                        ],
                    },
                },
            },
        }

    monkeypatch.setattr(github_client, "graphql_request", fake_graphql)
    threads = github_client.list_review_threads(7, "tok")
    assert [t["id"] for t in threads] == ["T1", "T2"]
    assert calls[0]["variables"]["after"] is None
    assert calls[1]["variables"]["after"] == "cursor1"


def test_resolve_review_thread_matches_comment_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """comment_id (REST 数値) を GraphQL thread 内の databaseId と突き合わせる."""
    mutation_calls: list[dict[str, Any]] = []

    def fake_list(pr_number: int, token: str) -> list[dict[str, Any]]:
        return [
            {
                "id": "T1",
                "isResolved": False,
                "comments": {"nodes": [{"databaseId": 100}, {"databaseId": 101}]},
            },
            {
                "id": "T2",
                "isResolved": False,
                "comments": {"nodes": [{"databaseId": 200}]},
            },
        ]

    def fake_graphql(
        query: str,
        variables: dict[str, Any],
        token: str,
    ) -> dict[str, Any]:
        mutation_calls.append({"query": query, "variables": variables})
        return {
            "resolveReviewThread": {
                "thread": {"id": variables["threadId"], "isResolved": True},
            },
        }

    monkeypatch.setattr(github_client, "list_review_threads", fake_list)
    monkeypatch.setattr(github_client, "graphql_request", fake_graphql)
    github_client.resolve_review_thread(7, 101, "tok")
    assert len(mutation_calls) == 1
    assert mutation_calls[0]["variables"]["threadId"] == "T1"


def test_resolve_review_thread_no_match_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_list(_pr: int, _tok: str) -> list[dict[str, Any]]:
        return [
            {
                "id": "T1",
                "isResolved": False,
                "comments": {"nodes": [{"databaseId": 100}]},
            },
        ]

    monkeypatch.setattr(github_client, "list_review_threads", fake_list)
    with pytest.raises(RuntimeError, match="Review thread not found for comment 999"):
        github_client.resolve_review_thread(7, 999, "tok")


# ============================================================================
# list_commit_check_runs (Issue #140)
# ============================================================================


def test_list_commit_check_runs_single_page(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    def fake_http_request(
        method: str,
        url: str,
        _token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> dict[str, Any]:
        captured.append(url)
        return {
            "total_count": 2,
            "check_runs": [
                {"name": "backend", "conclusion": "success"},
                {"name": "typegen-check", "conclusion": "failure"},
            ],
        }

    monkeypatch.setattr(github_client, "http_request", fake_http_request)
    runs = github_client.list_commit_check_runs(
        "https://api.github.com", "AME-Team/AME-AI-Review-System", "a" * 40, "tok"
    )
    assert [r["name"] for r in runs] == ["backend", "typegen-check"]
    assert captured == [
        "https://api.github.com/repos/AME-Team/AME-AI-Review-System/commits/"
        + "a" * 40
        + "/check-runs?per_page=100&page=1"
    ]


def test_list_commit_check_runs_paginates(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = iter([
        {"check_runs": [{"name": f"job{i}"} for i in range(100)]},
        {"check_runs": [{"name": "last"}]},
    ])

    def fake_http_request(
        _method: str,
        _url: str,
        _token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> Any:
        return next(pages)

    monkeypatch.setattr(github_client, "http_request", fake_http_request)
    runs = github_client.list_commit_check_runs(
        "https://api.github.com", "o/r", "b" * 40, "tok"
    )
    assert len(runs) == 101


def test_list_commit_check_runs_non_dict_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_http_request(
        _method: str,
        _url: str,
        _token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> Any:
        return ["unexpected"]

    monkeypatch.setattr(github_client, "http_request", fake_http_request)
    assert github_client.list_commit_check_runs("u", "o/r", "c" * 40, "tok") == []


def test_list_commit_check_runs_stops_at_page_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 異常応答が常に per_page 件返しても無限リクエストしない (Gate 1 指摘)。
    calls = 0

    def fake_http_request(
        _method: str,
        _url: str,
        _token: str,
        body: dict[str, Any] | None = None,
        **_kw: Any,
    ) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"check_runs": [{"name": f"job{calls}-{i}"} for i in range(100)]}

    monkeypatch.setattr(github_client, "http_request", fake_http_request)
    github_client.list_commit_check_runs("u", "o/r", "d" * 40, "tok")
    assert calls == github_client.MAX_CHECK_RUN_PAGES
