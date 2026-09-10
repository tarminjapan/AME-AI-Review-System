"""GitHub REST/GraphQL API 共通クライアント（main.py/reply.py/pr_streak.py 共通）."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, cast


class HttpError(RuntimeError):
    """GitHub API の HTTP エラー。ステータスコードを保持する."""

    def __init__(self, status_code: int, message: str) -> None:
        """HTTP ステータスコードとメッセージを保持する."""
        super().__init__(message)
        self.status_code = status_code


_REVIEW_THREADS_QUERY = """
query($owner: String!, $repo: String!, $pr: Int!, $after: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          comments(first: 100) {
            nodes { databaseId }
          }
        }
      }
    }
  }
}
"""

_RESOLVE_THREAD_MUTATION = """
mutation($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) {
    thread { id isResolved }
  }
}
"""


def resolve_env() -> tuple[str, str]:
    """GITHUB_API_URL と GITHUB_REPOSITORY を解決する."""
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        msg = "GITHUB_REPOSITORY environment variable is required"
        raise RuntimeError(msg)
    return api_url, repo


def _graphql_url() -> str:
    return os.environ.get("GITHUB_GRAPHQL_URL", "https://api.github.com/graphql")


def get_token(token_file: str, env_key: str = "GITHUB_PAT_TOKEN") -> str:
    """トークンファイル → 環境変数の優先順位でトークンを解決する."""
    path = Path(token_file).expanduser()
    if path.is_file():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = os.environ.get(env_key, "").strip()
    if token:
        return token
    msg = f"GitHub token not found: {path} or ${env_key}"
    raise RuntimeError(msg)


def bot_login(name: str) -> str:
    """GitHub App slug から bot の実際の login 名を返す.

    例: ``ame-ai-reviewer`` → ``ame-ai-reviewer[bot]``。
    本関数は GitHub App 運用を前提とする。すでに ``[bot]`` 付きの名前を渡した場合は
    二重付与を防ぐためそのまま返す。
    """
    return name if name.endswith("[bot]") else f"{name}[bot]"


_REVIEWER_LOGINS_CACHE: dict[tuple[str, str, str], set[str]] = {}

# 恒久的不許可 (GitHub App インストールトークンの GET /user は 401)。
# レート制限は 403 で返り得るため、403 はキャッシュ対象としない。
_HTTP_UNAUTHORIZED = 401


def clear_reviewer_logins_cache() -> None:
    """reviewer_logins のキャッシュを破棄する (テスト用・トークン切替用)."""
    _REVIEWER_LOGINS_CACHE.clear()


def reviewer_logins(api_url: str, token: str, reviewer_name: str) -> set[str]:
    """レビュアーが投稿し得る login の集合を返す.

    GitHub App 運用では ``{slug}[bot]`` で投稿されるが、PAT 運用ではトークン所有者の
    login になる (Issue #55 B5)。``GET /user`` で実投稿者を解決し、bot login との
    和集合を返す。解決失敗時は App 運用の後方互換として ``{slug}[bot]`` のみ返す。
    main.py / reply.py のレビュアー返信判定で共用する (Issue #92)。

    ``(api_url, token, reviewer_name)`` でキャッシュし、1 プロセス内で何度も
    ``GET /user`` を呼ばないようにする (reply.py のスレッド毎呼び出し対策)。

    - 成功時は常にキャッシュする。
    - 一時障害 (5xx / レート制限 403 等) はキャッシュせず、後続の呼び出しで再解決できる
      ようにする (一時障害時に ``[bot]`` 固定照合へ退行し Issue #92 が再発するのを防ぐ)。
    - 恒久的不許可 (401。GitHub App インストールトークンは ``GET /user`` が 401 に
      なる) のみキャッシュし、プロセス毎の無駄な API 呼び出しとエラーログノイズを避ける。
      403 はレート制限超過を伴い得るためキャッシュ対象としない (Gate 2 指摘対応)。
    """
    key = (api_url, token, reviewer_name)
    cached = _REVIEWER_LOGINS_CACHE.get(key)
    if cached is not None:
        return set(cached)

    logins = {bot_login(reviewer_name)}
    try:
        user = http_request("GET", f"{api_url}/user", token)
    except HttpError as exc:
        if exc.status_code == _HTTP_UNAUTHORIZED:
            # 401 は App トークン (恒久) と想定してキャッシュするが、PAT の誤設定等の
            # 一時的 401 を無言で隠さないよう一度だけ警告する (Gate 1 指摘対応)。
            print(
                f"[github_client] WARNING: GET /user returned 401; assuming "
                f"GitHub App token and falling back to {bot_login(reviewer_name)}. "
                "If this is a user PAT misconfiguration, clear the reviewer_logins "
                "cache or fix the token.",
                file=sys.stderr,
            )
            _REVIEWER_LOGINS_CACHE[key] = logins
        return logins
    except RuntimeError:
        return logins
    if isinstance(user, dict):
        user_dict: dict[str, Any] = cast("dict[str, Any]", user)
        login = user_dict.get("login")
        if isinstance(login, str):
            logins.add(login)
    _REVIEWER_LOGINS_CACHE[key] = logins
    return set(logins)


def mentions_reviewer(body: str, name: str) -> bool:
    """コメント本文がレビュアーへのメンションを含むかを判定する.

    GitHub App 運用時は ``@{slug}[bot]`` が正式形式だが、``@{slug}`` (``[bot]`` なし) でも
    GitHub 側で通知される場合があるため、両方の形式を受け入れる。
    """
    return f"@{name}" in body or f"@{bot_login(name)}" in body


def http_request(
    method: str,
    url: str,
    token: str,
    body: dict[str, Any] | None = None,
    accept: str = "application/vnd.github+json",
) -> Any:
    """GitHub REST/GraphQL 共通の HTTP 呼び出し."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", accept)
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        msg = f"GitHub API error {e.code} for {method} {url}: {detail}"
        raise HttpError(e.code, msg) from e
    if not raw:
        return None
    if accept == "application/vnd.github.diff":
        return raw
    return json.loads(raw)


def graphql_request(
    query: str, variables: dict[str, Any], token: str
) -> dict[str, Any]:
    """GraphQL リクエスト。HTTP 200 でも errors 配列を持ちうるため明示チェックする."""
    body = {"query": query, "variables": variables}
    result: object = http_request("POST", _graphql_url(), token, body=body)
    if not isinstance(result, dict):
        msg = f"Unexpected GraphQL response: {result!r}"
        raise TypeError(msg)
    result_dict = cast("dict[str, Any]", result)
    errors = result_dict.get("errors")
    if errors:
        msg = f"GraphQL errors: {errors}"
        raise RuntimeError(msg)
    data = result_dict.get("data")
    if not isinstance(data, dict):
        msg = f"Unexpected GraphQL response (no data): {result!r}"
        raise TypeError(msg)
    return cast("dict[str, Any]", data)


def list_review_threads(pr_number: int, token: str) -> list[dict[str, Any]]:
    """PR の全レビュースレッド（isResolved・コメント databaseId 含む）を取得する."""
    _, repo = resolve_env()
    owner, name = repo.split("/", 1)
    threads: list[dict[str, Any]] = []
    after: str | None = None
    while True:
        data = graphql_request(
            _REVIEW_THREADS_QUERY,
            {"owner": owner, "repo": name, "pr": pr_number, "after": after},
            token,
        )
        page = data["repository"]["pullRequest"]["reviewThreads"]
        threads.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    return threads


def resolve_review_thread(pr_number: int, comment_id: int, token: str) -> None:
    """comment_id を含むスレッドを特定し GraphQL mutation で Resolve する.

    GitHub REST にはスレッド Resolve に相当するエンドポイントが存在しないため GraphQL を使う。
    """
    for thread in list_review_threads(pr_number, token):
        ids = {c.get("databaseId") for c in thread["comments"]["nodes"]}
        if comment_id in ids:
            graphql_request(_RESOLVE_THREAD_MUTATION, {"threadId": thread["id"]}, token)
            return
    msg = f"Review thread not found for comment {comment_id}"
    raise RuntimeError(msg)


# Issue #140: Check Runs API のページング上限。API 異常で常に per_page 件返る場合の
# 無限リクエストを防ぐ (上限到達時は取得済み分で判定する fail-open)。
MAX_CHECK_RUN_PAGES = 10


def list_commit_check_runs(
    api_url: str, repo: str, ref: str, token: str
) -> list[dict[str, Any]]:
    """コミット (ref) の全 check runs を返す (ページング対応, Issue #140)."""
    owner, name = repo.split("/", 1)
    runs: list[dict[str, Any]] = []
    per_page = 100
    for page in range(1, MAX_CHECK_RUN_PAGES + 1):
        url = (
            f"{api_url}/repos/{owner}/{name}/commits/{ref}/check-runs"
            f"?per_page={per_page}&page={page}"
        )
        data = http_request("GET", url, token)
        if not isinstance(data, dict):
            break
        data_dict: dict[str, Any] = cast("dict[str, Any]", data)
        raw_runs = data_dict.get("check_runs")
        if not isinstance(raw_runs, list):
            break
        page_runs: list[dict[str, Any]] = cast("list[dict[str, Any]]", raw_runs)
        runs.extend(page_runs)
        if len(page_runs) < per_page:
            break
    return runs
