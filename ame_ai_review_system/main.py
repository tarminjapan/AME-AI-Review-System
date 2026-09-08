"""Main CLI entrypoint for AME AI Review System.

Replaces: pr_review.sh, checkout_pr.sh

Subcommands:
  review       Run AI review on PR (replaces pr_review.sh)
  checkout     Checkout PR branch (replaces checkout_pr.sh)
  setup        Install dependencies (replaces setup.sh)
  init         Bootstrap AME AI Review System in current repository
"""

from __future__ import annotations

import argparse
import contextlib
import math
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Callable

from . import diff_truncate, github_client, init_cmd, paths, pr_streak, review_config
from . import payload as payload_module
from .engine import apply_engine_info_env, resolve_settings, resolve_timeout

# ============================================================================
# Common utilities
# ============================================================================

PROJ_ROOT = paths.project_root()
# Issue #129: 収束シグナルの発火ラウンド。pr_max_reviews (既定 3) で最終レビューにも
# 発火するよう 2 (3 ラウンド目以降) としている。
STALE_ROUND_THRESHOLD = 2
HTTP_STATUS_OK = 200
# 除外ディレクトリのみの変更でスキップ通知を投稿する際の重複防止マーカー (PR 番号が付与される)。
SKIP_NOTICE_MARKER = "ame-review-skip-notice"
# Issue #129: レビュー回数上限到達通知の重複防止マーカー (PR 番号が付与される)。
LIMIT_NOTICE_MARKER = "ame-review-limit-notice"
# スキップ通知の既存判定で使うページサイズ / ページ上限。
SKIP_NOTICE_PAGE_SIZE = 100
SKIP_NOTICE_MAX_PAGES = 10


def _get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _reviewer_author_login(api_url: str, token: str, reviewer_name: str) -> str:
    """既レビュー判定に使う実際の投稿者 login を解決する.

    GitHub App 運用時はレビューが ``slug[bot]`` 名で投稿されるが、通常ユーザーの
    PAT で投稿すると PAT の持ち主の login になる (Issue #55 B5)。判定を
    ``bot_login(reviewer_name)`` 前提にすると PAT 運用で再レビューが毎回走るため、
    ``GET /user`` で実投稿者を解決する。失敗時は App 運用の後方互換として
    ``bot_login`` にフォールバックする。
    """
    logins = github_client.reviewer_logins(api_url, token, reviewer_name)
    bot = github_client.bot_login(reviewer_name)
    # 実投稿者 (bot login 以外) を優先して返す。和集合に実投稿者が無ければ bot。
    for login in logins:
        if login != bot:
            return login
    return bot


def _run_git(args: list[str], cwd: pathlib.Path | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd or PROJ_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def _run_git_check(
    args: list[str],
    cwd: pathlib.Path | None = None,
    timeout: float | None = None,
) -> tuple[bool, str]:
    """Git コマンドの成否と詳細 (stdout+stderr) を返す.

    ``_run_git`` は失敗を空文字で握り潰すため、成否判定が必要な箇所 (checkout 等) では
    こちらを使う (Issue #95)。

    ``timeout`` を明示しない場合の既定は 30 秒 (``_run_git`` と同一)。大規模リポジトリの
    ``git fetch`` のように 30 秒を超え得る処理は、呼び出し側で ``_git_timeout()``
    (既定 300、``GIT_TIMEOUT_SECONDS`` で制御) を明示して使う (Gate 1 指摘対応)。
    """
    timeout_seconds = timeout if timeout is not None else 30.0
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd or PROJ_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    detail = (result.stdout + result.stderr).strip()
    return result.returncode == 0, detail


def _git_ref_check(
    command: str,
    ref: str,
    cwd: pathlib.Path | None = None,
    timeout: float | None = None,
    extra_args: list[str] | None = None,
) -> tuple[bool, str]:
    """検証済み refname をリスト引数で git へ渡す薄いヘルパー (Gate 1 指摘対応).

    ``_is_valid_ref_name`` の結果は必ず subprocess のリスト引数 (シェル境界を通らない)
    として渡すというセキュリティ契約を、本ヘルパーへ集約して機械的に守る。検証済みの
    ``ref`` から ``[command, *extra_args, ref]`` を内部生成するため、呼び出し側が
    args と検証対象 ref を二重管理して乖離する余地がない。将来呼び出し側が
    ``shell=True`` や文字列補間を誤用しても、このヘルパー経由なら検証済み ref のみが
    渡る。
    """
    if not _is_valid_ref_name(ref):
        return False, f"invalid refname: {ref!r}"
    args = [command, *(extra_args or []), ref]
    return _run_git_check(args, cwd=cwd, timeout=timeout)


def _git_timeout() -> float:
    """``git fetch`` など大規模処理向けのタイムアウトを返す (既定 300).

    ``_run_git_check`` の既定 (30 秒) を超え得る fetch にのみ使用し、checkout 等の
    軽量操作は既定のままとする (Gate 1 指摘対応)。

    ``inf`` / ``nan`` (``GIT_TIMEOUT_SECONDS=inf`` 等) は subprocess のタイムアウトに
    渡すとプラットフォーム依存で OverflowError を誘発し得るため、``math.isfinite`` で
    既定へフォールバックする (Gate 1 指摘対応)。
    """
    raw = os.environ.get("GIT_TIMEOUT_SECONDS", "300")
    try:
        value = float(raw)
    except ValueError:
        return 300.0
    if not math.isfinite(value):
        return 300.0
    return value if value > 0 else 300.0


def _is_valid_ref_name(name: str) -> bool:
    r"""Git の refname として安全なブランチ名かを判定する (Issue #95).

    ``git check-ref-format`` の規約に倣う (先頭ドット禁止・``..``/``@{``/空白/``~``/
    ``^``/``:``/``?``/``*``/``[``/``\`` 禁止・``/`` 始まりと ``//`` 禁止・``@`` 単体
    禁止)。subprocess はリスト引数で起動されるためシェルメタ文字の展開は無く、
    git が許可する文字 (``(`` / ``)`` / ``%`` / ``,`` / ``{`` / ``}`` / ``;`` /
    ``$`` 等) を含むブランチ名 (例: ``fix(issue)``) を拒否しない (Gate 2 指摘対応)。

    **セキュリティ契約**: 本関数の結果は必ず ``subprocess.run`` のリスト引数
    (シェル境界を通らない) として渡すこと。``shell=True`` やシェル文字列補間、
    他プロセスの入力に流す改修を入れた場合は、この検証ではインジェクションを防げない
    ため、呼び出し側でその経路を作らないこと (Gate 1 指摘対応)。
    """
    if not name or name == "@":
        return False
    # 先頭ハイフンは git がオプションとして解釈するため拒否 (オプション注入対策)。
    if name.startswith(("-", ".", "/")):
        return False
    if name.endswith(("/", ".", ".lock")):
        return False
    if ".." in name or "//" in name or "\\" in name:
        return False
    if "@{" in name:
        return False
    # コンポーネント単位の規約: 先頭ドット (feature/.bar) と .lock 終端の
    # コンポーネント (feature/foo.lock) は git check-ref-format で不正 (Gate 1 指摘対応)。
    # 全体の先頭ドットは name.startswith(("-", ".", "/")) で既に拒否済み。
    if "/." in name:
        return False
    if any(part.endswith(".lock") for part in name.split("/")):
        return False
    # git が refname で禁止する文字と、制御文字・空白のみを拒否する。
    return not any(ch in name for ch in " ~\t^:?*[\\") and not any(
        ch < "\x20" or ch == "\x7f" for ch in name
    )


# ============================================================================
# checkout command (replaces checkout_pr.sh)
# ============================================================================


def cmd_checkout(args: argparse.Namespace) -> int:
    api_url, repo = github_client.resolve_env()
    pr_number = args.pr_number
    try:
        token = args.token or github_client.get_token(
            str(
                pathlib.Path.home()
                / ".config"
                / "ame-ai-review-system"
                / "github.token"
            ),
        )
    except RuntimeError:
        token = ""

    if not token:
        print("[checkout] ERROR: Token required", file=sys.stderr)
        return 1

    # Fetch PR info
    pr_url = f"{api_url}/repos/{repo}/pulls/{pr_number}"
    try:
        pr_data = github_client.http_request("GET", pr_url, token)
    except RuntimeError as e:
        print(f"[checkout] ERROR: Failed to fetch PR info: {e}", file=sys.stderr)
        return 1

    if not isinstance(pr_data, dict):
        print(
            f"[checkout] ERROR: Unexpected PR data type: {type(pr_data)}",
            file=sys.stderr,
        )
        return 1

    pr_dict = cast("dict[str, Any]", pr_data)
    base_ref = cast("str", pr_dict.get("base", {}).get("ref", ""))
    if not _is_valid_ref_name(base_ref):
        print(f"[checkout] ERROR: Invalid BASE_REF: {base_ref!r}", file=sys.stderr)
        return 1

    title = cast("str", pr_dict.get("title", ""))
    body = cast("str", pr_dict.get("body", ""))
    head_branch = cast("str", pr_dict.get("head", {}).get("ref", ""))

    if not head_branch or head_branch == "HEAD":
        print(
            f"[checkout] ERROR: Could not determine head branch for PR #{pr_number}",
            file=sys.stderr,
        )
        return 1

    if not _is_valid_ref_name(head_branch):
        print(
            f"[checkout] ERROR: Invalid head branch: {head_branch!r}", file=sys.stderr
        )
        return 1

    # Write metadata to GITHUB_ENV if available
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        delim = "ame_review_meta"
        with pathlib.Path(github_env).open("a", encoding="utf-8") as f:
            f.writelines(
                f"{key}<<{delim}\n{value}\n{delim}\n"
                for key, value in (
                    ("BASE_REF", base_ref),
                    ("PR_TITLE", title),
                    ("PR_BODY", body),
                )
            )

    # Fetch and checkout
    # _git_ref_check が refname 検証とリスト引数起動 (シェル境界を通らない) を一体で
    # 保証する。fetch は大規模リポジトリで 30 秒を超え得るため、長めのタイムアウトを
    # 明示する (GIT_TIMEOUT_SECONDS で制御、既定 300)。checkout は既定 (30 秒)。
    ok, detail = _git_ref_check(
        "fetch",
        head_branch,
        extra_args=["origin"],
        timeout=_git_timeout(),
    )
    if not ok:
        print(
            f"[checkout] ERROR: git fetch origin {head_branch!r} failed: {detail}",
            file=sys.stderr,
        )
        return 1
    # checkout も _git_ref_check 経由で検証済み refname をリスト引数で渡す。
    ok, detail = _git_ref_check("checkout", head_branch)
    if not ok:
        print(
            f"[checkout] ERROR: git checkout {head_branch!r} failed: {detail}",
            file=sys.stderr,
        )
        return 1

    print(
        f"[checkout] Checked out PR #{pr_number} branch '{head_branch}' (base: {base_ref})",
    )
    return 0


# ============================================================================
# review command (replaces pr_review.sh)
# ============================================================================


def _build_review_prompt(
    pr_number: int,
    pr_title: str,
    base_ref: str,
    pr_body: str,
    changed_files: str,
    commit_log: str,
    diff: str,
    review_count: int,
    reviewer_prompt_file: pathlib.Path,
) -> str:
    """Build the review prompt for the AI engine."""
    prompt_lines = [
        reviewer_prompt_file.read_text(encoding="utf-8"),
        "",
        "## PR 情報",
        f"- PR #: {pr_number}",
        f"- タイトル: {pr_title}",
        f"- マージ先: {base_ref}",
        f"- 説明: {pr_body or '（なし）'}",
    ]

    if review_count >= STALE_ROUND_THRESHOLD:
        prompt_lines += [
            "",
            f"## ⚠️ 収束シグナル（ラウンド {review_count + 1}）",
            f"この PR は既に {review_count} 回レビュー済みです。",
            "新規機能追加の指摘や些末な改善提案は抑制し、",
            "既存指摘への対応確認と CRITICAL/HIGH のみに集中してください。",
        ]

    prompt_lines += [
        "",
        "## 変更ファイル一覧",
        "```",
        changed_files,
        "```",
        "",
        "## コミット一覧",
        "```",
        commit_log,
        "```",
        "",
        "## diff",
        "```diff",
        diff,
        "```",
    ]
    # Issue #47: 除外した vendored パッケージが参照されている場合は、存在を注記して
    # 「モジュール不存在」という誤指摘を防ぐ。
    review_config.append_reference_note(
        prompt_lines,
        [f for f in changed_files.splitlines() if f.strip()],
        diff,
    )
    return "\n".join(prompt_lines)


def _run_engine_capture(
    _settings: dict[str, Any],
    prompt: str,
    *,
    show_info: bool = True,
) -> tuple[int, str, str]:
    """Run engine.py with prompt, return (exit_code, stdout, stderr)."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix="_prompt.txt",
        delete=False,
        encoding="utf-8",
    ) as pf:
        pf.write(prompt)
        prompt_file = pf.name

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix="_out.txt",
        delete=False,
        encoding="utf-8",
    ) as of:
        out_file = of.name

    err_file = out_file + ".err"

    # Issue #94: engine.py と同じ解決経路 (REVIEW_TIMEOUT_SECONDS 既定 600) を親の
    # subprocess にも適用する。reply.py と経路を統一し、ハードコード 600 や
    # settings 由来の乖離を防ぐ。
    timeout = resolve_timeout()

    # Issue #40: Gate 2 のエンジン情報バナー表示フラグを子プロセスへ注入する。
    engine_env = dict(os.environ)
    apply_engine_info_env(engine_env, show_info=show_info)

    try:
        with (
            pathlib.Path(prompt_file).open(encoding="utf-8") as pfi,
            pathlib.Path(out_file).open("w", encoding="utf-8") as fout,
            pathlib.Path(err_file).open("w", encoding="utf-8") as efi,
        ):
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ame_ai_review_system.engine",
                    "--role",
                    "review",
                ],
                stdin=pfi,
                stdout=fout,
                stderr=efi,
                env=engine_env,
                timeout=timeout,
                check=False,
            )
        engine_exit = proc.returncode

        stdout = pathlib.Path(out_file).read_text(encoding="utf-8")
        stderr = pathlib.Path(err_file).read_text(encoding="utf-8")

        return engine_exit, stdout, stderr
    finally:
        for f in (prompt_file, out_file, err_file):
            with contextlib.suppress(OSError):
                pathlib.Path(f).unlink()


def _post_review(
    api_url: str,
    repo: str,
    pr_number: int,
    token: str,
    payload_data: dict[str, Any],
) -> tuple[int, dict[str, Any] | list[Any]]:
    """Post a review to GitHub. Returns (status_code, response_json)."""
    url = f"{api_url}/repos/{repo}/pulls/{pr_number}/reviews"
    try:
        resp = github_client.http_request("POST", url, token, body=payload_data)
    except github_client.HttpError as e:
        print(
            f"[review] Failed to post review (HTTP {e.status_code}): {e}",
            file=sys.stderr,
        )
        return e.status_code, {}
    except RuntimeError as e:
        print(f"[review] Failed to post review: {e}", file=sys.stderr)
        return 0, {}
    else:
        return 200, resp


def skip_notice_already_posted(
    comments: list[dict[str, Any]],
    marker: str,
    issue_url: str,
) -> bool:
    """対象 PR 向けのスキップ通知が既に投稿済みか判定する."""
    normalized_issue_url = issue_url.rstrip("/")
    return any(
        marker in str(c.get("body", ""))
        and str(c.get("issue_url", "")).rstrip("/") == normalized_issue_url
        for c in comments
    )


def _post_skip_notice(api_url: str, repo: str, pr_number: int, token: str) -> None:
    """レビュー対象外スキップの通知を PR へ一度だけ投稿する."""
    # スキップ理由を PR へ通知して /request-review が無視されたことを可視化する。
    # マーカー付きコメントを一度だけ投稿し、再リクエストでの重複を防ぐ。
    notice_url = f"{api_url}/repos/{repo}/issues/{pr_number}/comments"
    # PR 番号入りマーカーで他 PR の通知と混同しない。
    marker = f"{SKIP_NOTICE_MARKER}-pr{pr_number}"
    issue_url = f"{api_url}/repos/{repo}/issues/{pr_number}"
    try:
        # 高速パス: リポジトリ横断の降順クエリで直近100件から判定 (1リクエスト)。
        existing = github_client.http_request(
            "GET",
            f"{api_url}/repos/{repo}/issues/comments"
            f"?sort=created&direction=desc&per_page={SKIP_NOTICE_PAGE_SIZE}",
            token,
        )
        if isinstance(existing, list):
            already_posted = skip_notice_already_posted(
                cast("list[dict[str, Any]]", existing),
                marker,
                issue_url,
            )
        else:
            print(
                f"[review] Unexpected comments response type: "
                f"{type(existing).__name__}",
                file=sys.stderr,
            )
            already_posted = False
        # 直近100件に無い場合は PR スコープを全ページ走査して確実に判定する。
        if not already_posted:
            page = 1
            while page <= SKIP_NOTICE_MAX_PAGES:
                resp = github_client.http_request(
                    "GET",
                    f"{notice_url}?per_page={SKIP_NOTICE_PAGE_SIZE}&page={page}",
                    token,
                )
                if not isinstance(resp, list) or not resp:
                    break
                resp_list = cast("list[dict[str, Any]]", resp)
                if skip_notice_already_posted(resp_list, marker, issue_url):
                    already_posted = True
                    break
                if len(resp_list) < SKIP_NOTICE_PAGE_SIZE:
                    break
                page += 1
    except RuntimeError as e:
        print(
            f"[review] Failed to check existing skip notice: {e}",
            file=sys.stderr,
        )
        return
    if already_posted:
        print("[review] Skip notification already posted; skipping.")
        return
    # チェック→投稿は REST 上アトミックではないが、マーカー確認で重複の
    # 実害を実用上ほぼ排除できる (ベストエフォート)。
    body = (
        "**レビュー対象外**\n\n"
        "変更が `ame_ai_review_system/` 配下のみのため、AI レビューをスキップしました "
        "(Issue #37)。`.ame-review/config.json` の `review_include_package_dir` を "
        "`true` にすると対象になります。\n\n"
        f"<!-- {marker} -->"
    )
    try:
        github_client.http_request(
            "POST",
            notice_url,
            token,
            body={"body": body},
        )
    except RuntimeError as e:
        print(f"[review] Failed to notify skip reason: {e}", file=sys.stderr)


def _post_limit_notice(
    api_url: str,
    repo: str,
    pr_number: int,
    token: str,
    max_reviews: int,
) -> None:
    """Gate 2 のレビュー回数上限到達を PR へ一度だけ通知する.

    ``pr_max_reviews`` (Issue #129) に達してレビューをスキップすると PR 上では
    無言のまま review が止まるため、開発者が「なぜ黙ったか」を把握できるよう
    マーカー付きコメントを一度だけ投稿する。重複防止は対象 PR にスコープした
    issue コメントをページング走査して判定する (リポジトリ全体の直近 N 件ではなく
    PR 単位で判定することで、アクティブなリポジトリでも確実に検知できる)。
    """
    notice_url = f"{api_url}/repos/{repo}/issues/{pr_number}/comments"
    marker = f"{LIMIT_NOTICE_MARKER}-pr{pr_number}"
    issue_url = f"{api_url}/repos/{repo}/issues/{pr_number}"
    try:
        already_posted = False
        page = 1
        while page <= SKIP_NOTICE_MAX_PAGES:
            resp = github_client.http_request(
                "GET",
                f"{notice_url}?per_page={SKIP_NOTICE_PAGE_SIZE}&page={page}",
                token,
            )
            if not isinstance(resp, list) or not resp:
                break
            resp_list = cast("list[dict[str, Any]]", resp)
            if skip_notice_already_posted(resp_list, marker, issue_url):
                already_posted = True
                break
            if len(resp_list) < SKIP_NOTICE_PAGE_SIZE:
                break
            page += 1
    except RuntimeError as e:
        print(
            f"[review] Failed to check existing limit notice: {e}",
            file=sys.stderr,
        )
        return
    if already_posted:
        print("[review] Limit notification already posted; skipping.")
        return
    body = (
        "**AI レビュー回数上限に到達しました**\n\n"
        f"この PR は既に {max_reviews} 回レビュー済みのため、"
        "`pr_max_reviews` の上限に従い Gate 2 を終了します。\n"
        "指摘への対応状況を確認の上、必要に応じて手動でマージしてください "
        "(上限は `config.json` の `pr_max_reviews` で変更できます)。\n\n"
        f"<!-- {marker} -->"
    )
    try:
        github_client.http_request(
            "POST",
            notice_url,
            token,
            body={"body": body},
        )
    except RuntimeError as e:
        print(f"[review] Failed to notify review limit: {e}", file=sys.stderr)


def _run_engine_text(
    prompt: str,
    settings: dict[str, Any],
    *,
    show_info: bool = True,
) -> str | None:
    return payload_module.engine_output_text(
        _run_engine_capture(settings, prompt, show_info=show_info)
    )


def _build_review_payloads(
    review_json: str,
    base_ref: str,
    head_sha: str,
    repair: Callable[[str], str | None] | None = None,
    max_attempts: int | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Parse review JSON and build GitHub review payloads.

    ``(payloads, is_fallback)`` を返す。``is_fallback`` は JSON パース失敗時に真。
    """
    review, is_fallback = payload_module.parse_review_json_with_flag(
        review_json,
        repair=repair,
        max_attempts=max_attempts,
    )
    valid_lines = payload_module.build_valid_lines_map(base_ref)
    payloads = payload_module.build_review_payloads(
        review,
        valid_lines,
        head_sha,
        is_fallback=is_fallback,
    )
    return payloads, is_fallback


def cmd_review(args: argparse.Namespace) -> int:
    api_url, repo = github_client.resolve_env()
    pr_number = args.pr_number
    base_ref = args.base_ref
    pr_title = args.pr_title or ""
    pr_body = args.pr_body or ""
    reviewer_name = _get_env("REVIEWER_NAME", "ame-ai-reviewer")
    reviewer_prompt_file = args.prompt_file or paths.prompt_path()

    # Token resolution
    try:
        token = args.token or github_client.get_token(
            str(
                pathlib.Path.home()
                / ".config"
                / "ame-ai-review-system"
                / f"{reviewer_name}.token",
            ),
            reviewer_name.upper().replace("-", "_") + "_TOKEN",
        )
    except RuntimeError:
        token = ""
    if not token:
        print("[review] ERROR: REVIEWER_TOKEN not found", file=sys.stderr)
        return 1

    # PR streak check
    if pr_streak.cmd_check(pr_number) == 0:
        print(
            f"[review] PR #{pr_number} already approved (streak threshold). Skipping review.",
        )
        return 0

    # Get HEAD SHA
    head_sha = _run_git(["rev-parse", "HEAD"])
    if not head_sha:
        print("[review] ERROR: Failed to get HEAD SHA.", file=sys.stderr)
        return 1

    # Check already reviewed SHAs
    reviews_url = f"{api_url}/repos/{repo}/pulls/{pr_number}/reviews?per_page=100"
    try:
        reviews_data = github_client.http_request("GET", reviews_url, token)
    except RuntimeError:
        reviews_data = []

    if not isinstance(reviews_data, list):
        reviews_data = []

    # Issue #55 B5: App bot 前提の bot_login 照合では PAT 運用で重複レビューが
    # 発生するため、実投稿者 login を解決して判定する。混在運用 (bot と PAT の両方で
    # 投稿) でも過去の reviewed-sha を拾えるよう、bot login との和集合で照合する。
    reviewer_login = _reviewer_author_login(api_url, token, reviewer_name)
    accepted_logins = {reviewer_login, github_client.bot_login(reviewer_name)}
    reviewed_shas: set[str] = set()
    for r in cast("list[dict[str, Any]]", reviews_data):
        if r.get("user", {}).get("login") in accepted_logins:
            body = cast("str", r.get("body", ""))
            m = re.search(r"<!--\s*reviewed-sha:\s*([0-9a-f]{40,64})\s*-->", body)
            if m:
                reviewed_shas.add(m.group(1))

    if head_sha in reviewed_shas:
        print(f"[review] Already reviewed HEAD SHA {head_sha[:8]}, skipping.")
        return 0

    # Issue #129: 総レビュー回数のハード上限。LOW 連続の有無に関わらず、この回数に
    # 達したらそれ以降の PR レビューはスキップして Gate 2 を終了する。上限到達は
    # 開発者が把握できるよう PR へ一度だけ通知する。
    max_reviews = review_config.pr_max_reviews()
    if len(reviewed_shas) >= max_reviews:
        print(
            f"[review] Already {len(reviewed_shas)} push review(s) "
            f"(max {max_reviews}), skipping.",
        )
        if token:
            _post_limit_notice(api_url, repo, pr_number, token, max_reviews)
        return 0

    # Get diff and changed files
    # Issue #55 I1: diff の狭域化 (diff_base) はローカル pre-commit 用途に限定する。
    # PR レビューは GitHub review API の line 検証が PR 実ベースの diff 位置で行われる
    # ため、従来どおり origin/{base}...HEAD を維持する。
    diff = _run_git(["diff", f"origin/{base_ref}...HEAD"])
    if not diff:
        diff = _run_git(["diff", "HEAD~1"])
    if not diff:
        print("[review] No diff found, skipping review.")
        return 0

    # Diff compression via diff_utils
    try:
        from . import diff_utils

        diff = diff_utils.compact_diff(diff)
    except ImportError:
        pass

    # Issue #37: 移植先で vendored した ame_ai_review_system 配下はレビュー対象外
    diff = review_config.filter_review_diff(diff)
    if not diff.strip():
        print("[review] No diff outside ame_ai_review_system. Skipping review.")
        if token:
            _post_skip_notice(api_url, repo, pr_number, token)
        return 0

    # Issue #62: 共通切り捨てモジュールで戦略的に圧縮。PR レビューは優先サブセットが
    # 無いため head+tail 保持で後方ファイル (CSS/types/tests) を可視化する。
    config = review_config.load_config()
    diff_lines = diff.count("\n")
    if diff_lines > review_config.max_diff_lines(config):
        print(
            f"[review] Diff truncated from {diff_lines} to "
            f"{review_config.max_diff_lines(config)} lines "
            f"(strategy={review_config.diff_truncation_strategy(config)}).",
        )
        diff = diff_truncate.truncate_diff(
            diff,
            max_lines=review_config.max_diff_lines(config),
            strategy=review_config.diff_truncation_strategy(config),
            context_floor=review_config.diff_truncation_context_lines(config),
        )

    changed_files = _run_git(["diff", "--name-only", f"origin/{base_ref}...HEAD"])
    if not changed_files:
        changed_files = _run_git(["diff", "--name-only", "HEAD~1"])
    # Issue #37: 除外対象ディレクトリ配下を除去 (変更ファイルは最大50件まで)
    changed_files = "\n".join(
        review_config.filter_review_targets(
            [f for f in changed_files.splitlines() if f.strip()],
        )[:50],
    )

    commit_log = _run_git(["log", f"origin/{base_ref}..HEAD", "--oneline"])
    if not commit_log:
        commit_log = _run_git(["log", "HEAD~20..HEAD", "--oneline"])

    # Circuit breaker: static analysis pre-check
    if review_config.load_config().get("pr_review_require_static_checks", True):
        print("[review] Running static analysis pre-check (ruff/mypy/semgrep)...")
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ame_ai_review_system.static_precheck",
                    "--files-from-stdin",
                ],
                input=changed_files.encode(),
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                print("[review] Static analysis failed. Skipping AI review.")
                print(
                    "[review] 静的解析エラーを解消してから /request-review を再実行してください。",
                )
                return 0
        except (subprocess.SubprocessError, OSError) as e:
            print(f"[review] Static precheck error: {e}", file=sys.stderr)
            return 1
        print("[review] Static analysis passed. Proceeding to AI review.")

    # Build prompt
    prompt = _build_review_prompt(
        pr_number=pr_number,
        pr_title=pr_title,
        base_ref=base_ref,
        pr_body=pr_body,
        changed_files=changed_files,
        commit_log=commit_log,
        diff=diff,
        review_count=len(reviewed_shas),
        reviewer_prompt_file=pathlib.Path(reviewer_prompt_file),
    )

    # Run engine
    print("[review] Running review via engine.py...")
    settings = resolve_settings("review")
    # Issue #40: Gate 2 のエンジン情報表示トグル (既定=表示)。
    show_info = review_config.config_bool(
        review_config.load_config(),
        "show_engine_info_gate2",
        default=True,
    )
    if settings["engine"] != "claude" and show_info:
        print(
            f"[review] WARNING: budget limit not enforced for {settings['engine']}",
            file=sys.stderr,
        )

    engine_exit, engine_out, engine_err = _run_engine_capture(
        settings,
        prompt,
        show_info=show_info,
    )

    if engine_err:
        print(f"[review] Engine stderr: {engine_err}", file=sys.stderr)

    if engine_exit != 0 or not engine_out.strip():
        print("[review] Engine failed.", file=sys.stderr)
        return 1

    print(f"[review] Engine output captured ({len(engine_out)} bytes)")

    # Write engine output to temp file for payload parser
    review_file: pathlib.Path | None = None
    try:
        fd, review_path = tempfile.mkstemp(suffix=".json", prefix="review_")
        os.close(fd)
        review_file = pathlib.Path(review_path)
        review_file.write_text(engine_out, encoding="utf-8")
        payloads, is_fallback = _build_review_payloads(
            str(review_file),
            base_ref,
            head_sha,
            repair=lambda broken: payload_module.repair_review_json(
                broken,
                lambda p: _run_engine_text(
                    p,
                    review_config.apply_repair_model(settings),
                    show_info=show_info,
                ),
            ),
            max_attempts=review_config.max_repair_attempts(),
        )
        if is_fallback:
            print(
                "[review] JSON parse failed after repair attempts; "
                "posting retry-request summary without reviewed-sha marker.",
                file=sys.stderr,
            )
    except (ValueError, KeyError, TypeError, OSError) as e:
        print(f"[review] Failed to build payload: {e}", file=sys.stderr)
        return 1
    finally:
        if review_file is not None:
            review_file.unlink(missing_ok=True)

    if not payloads:
        print("[review] No payloads built.")
        return 0

    # Post reviews
    print(
        f"[review] Posting {len(payloads)} review(s) to PR #{pr_number} as {reviewer_name}...",
    )

    for i, pl in enumerate(payloads):
        status, resp = _post_review(api_url, repo, pr_number, token, pl)
        review_id = resp.get("id", "?") if isinstance(resp, dict) else "?"
        if status == HTTP_STATUS_OK:
            print(
                f"[review] Review {i + 1}/{len(payloads)} posted (id={review_id}, HTTP {status}).",
            )
        else:
            print(
                f"[review] Failed to post review {i + 1}/{len(payloads)} (HTTP {status}).",
            )
            # Try fallback as general comment
            if pl.get("comments"):
                fallback = pl.copy()
                bodies = [c.get("body", "") for c in pl["comments"]]
                fallback["body"] = "\n\n---\n\n".join(bodies)
                fallback["comments"] = []
                fb_status, _ = _post_review(api_url, repo, pr_number, token, fallback)
                if fb_status == HTTP_STATUS_OK:
                    print(
                        f"[review] Review {i + 1} posted as general comment (HTTP {fb_status}).",
                    )
                else:
                    print(f"[review] Fallback also failed (HTTP {fb_status}).")

    return 0


# ============================================================================
# setup command (replaces setup.sh)
# ============================================================================


def cmd_setup(_args: argparse.Namespace) -> int:
    """Install dependencies and configure pre-commit hooks."""
    import shutil

    if shutil.which("uv") is None:
        print(
            "[setup] ERROR: uv not found on PATH. Install it first: "
            "https://docs.astral.sh/uv/",
            file=sys.stderr,
        )
        return 1
    if os.environ.get("VIRTUAL_ENV") is None:
        print(
            "[setup] ERROR: no active venv. Create and activate one first: "
            "uv venv .venv --python 3.12 && source .venv/bin/activate",
            file=sys.stderr,
        )
        return 1

    # pre-commit の language: system フックは ruff / mypy 等を直接呼ぶため、
    # ツールを isolated な ~/.local/bin へ入れると PATH 依存で実行に失敗する。
    # requirements-dev.txt（正本）をアクティブな venv へ入れて .venv/bin 経由で
    # 呼べるようにする。
    print("[setup] Installing Python dev tools into the active venv...")
    try:
        subprocess.run(
            ["uv", "pip", "install", "-r", str(PROJ_ROOT / "requirements-dev.txt")],
            check=True,
            cwd=PROJ_ROOT,
        )
    except subprocess.CalledProcessError as exc:
        print(f"[setup] ERROR: uv pip install failed: {exc}", file=sys.stderr)
        return 1

    print("[setup] Installing Node.js dev tools...")
    subprocess.run(["npm", "ci"], check=False, cwd=PROJ_ROOT)

    print("[setup] Installing pre-commit hooks...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pre_commit",
            "install",
            "--install-hooks",
            "-t",
            "pre-commit",
            "-t",
            "commit-msg",
            "-t",
            "pre-push",
        ],
        check=False,
        cwd=PROJ_ROOT,
    )

    print("[setup] Done. Run: pre-commit run --all-files")
    return 0


# ============================================================================
# Main entrypoint
# ============================================================================


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AME AI Review System CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # checkout
    p_checkout = subparsers.add_parser("checkout", help="Checkout PR branch")
    p_checkout.add_argument("pr_number", type=int)
    p_checkout.add_argument("--token", help="GitHub token (or use token file/env)")

    # review
    p_review = subparsers.add_parser("review", help="Run AI review on PR")
    p_review.add_argument("pr_number", type=int)
    p_review.add_argument(
        "--base-ref",
        default=os.environ.get("BASE_REF", "main"),
    )
    p_review.add_argument("--pr-title", default="")
    p_review.add_argument("--pr-body", default="")
    p_review.add_argument(
        "--prompt-file",
        type=pathlib.Path,
        help="Reviewer prompt file",
    )
    p_review.add_argument("--token", help="Reviewer token (or use token file/env)")

    # setup
    subparsers.add_parser("setup", help="Install dependencies and configure hooks")

    # init
    p_init = subparsers.add_parser(
        "init",
        help="Bootstrap AME AI Review System in current repository",
    )
    p_init.add_argument(
        "--preset",
        choices=["full", "minimal", "python", "text", "ts", "auto"],
        default="auto",
        help="pre-commit static analysis preset (default: auto = package.jsonが"
        "あれば ts、なければ full; Issue #69)",
    )
    p_init.add_argument(
        "--python",
        default=None,
        help="Gate 1 フックを language: system で生成するときに埋め込む "
        "Python インタープリタパス (オフライン向け。default: AME_INIT_PYTHON "
        "env or sys.executable; Issue #66/#79)",
    )
    p_init.add_argument(
        "--engine",
        default=None,
        choices=init_cmd.ENGINE_CHOICES,
        help="Gate 1 の既定 LLM エンジン。claude/antigravity は additional_dependencies "
        "へ Python SDK を追加して pre-commit の隔離 venv で利用可能にする (Issue #114)。"
        "未指定時は AME_INIT_ENGINE → auto (自動検出)",
    )
    p_init.add_argument(
        "--version",
        default=None,
        help="Gate 1 フックが参照する wheel のバージョン "
        "(default: インストール済みパッケージの __version__; Issue #79/#84)",
    )
    p_init.add_argument(
        "--ref",
        default=None,
        help="GitHub ref for reusable workflows (required unless --no-workflow)",
    )
    p_init.add_argument(
        "--no-workflow",
        action="store_true",
        help="Skip generating CI wrapper workflows",
    )
    p_init.add_argument(
        "--with-engines",
        action="store_true",
        help="Install TS engine sidecar (.ame-review/engines-ts)",
    )
    p_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )

    args = parser.parse_args(argv)

    if args.command == "checkout":
        return cmd_checkout(args)
    if args.command == "review":
        return cmd_review(args)
    if args.command == "setup":
        return cmd_setup(args)
    if args.command == "init":
        return init_cmd.cmd_init(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
