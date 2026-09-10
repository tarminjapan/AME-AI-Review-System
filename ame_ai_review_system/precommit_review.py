from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Any, cast

from . import (
    diff_base,
    diff_truncate,
    paths,
    payload,
    precommit_engine,
    precommit_state,
    review_config,
    stale_detect,
)

# Issue #62: ステージ済み差分セクションを全行保持するための優先マーカー。
# _build_diff が出力する "### ステージ済み差分 ..." ヘッダに対応する。
_PRIORITY_DIFF_MARKER = "ステージ済み差分"

# LOW/INFO のみの指摘が連続した回数の閾値 (固定, Issue #134)。Gate 2 の
# ``pr_streak._STREAK_THRESHOLD`` と共有定数 ``review_config.LOW_STREAK_THRESHOLD``
# を参照し、片方だけ変更されて非対称化するのを防ぐ。
_LOW_STREAK_THRESHOLD = review_config.LOW_STREAK_THRESHOLD

# 重大度によらない総レビュー回数の上限は ``precommit_max_reviews`` (config.json,
# 既定 3) で制御する。blocking 指摘が残っていてもこの回数に達したらコミットを
# 許可する (Issue #134)。_decide が None のとき内部的に review_config から解決する。

# エンジン失敗 streak がこの回数に達したらコミットを許可する（API 一時障害対策）。
_ENGINE_FAILURE_STREAK_THRESHOLD = 3

# fail-closed 方針: LOW/INFO 以外の severity (CRITICAL/HIGH/MIDDLE/WARNING/typo/未知) は
# すべて blocking 扱い。LLM が規格外の severity を吐いても確認を挟む。
_LOW_SEVERITIES = ("LOW", "INFO")

# engine.py 内部のタイムアウト(600s) + バッファ。外側の python3 プロセス自体が
# ハングした場合にコミットを永遠にブロックしないための上限。
_ENGINE_TIMEOUT_SECONDS = 660

# ruff / mypy のタイムアウト。LLM レビュー前にコード品質を保証するための pre-check。
_STATIC_CHECK_TIMEOUT_SECONDS = 120


def _staged_files() -> list[str]:
    out = precommit_state.run_git([
        "diff",
        "--cached",
        "--name-only",
        "--diff-filter=d",
    ])
    return [line.strip() for line in out.splitlines() if line.strip()]


# Issue #55 B1: テストのみのステージ時にテスト対象モジュールの実装コンテキストを
# diff へ追加するためのテストファイル判定・パス対応ヒューリスティック。
# include_test_target_diff が true のときのみ有効化する (既定 false)。


def _is_test_file(path: str) -> bool:
    if not path.endswith(".py"):
        return False
    name = path.rsplit("/", 1)[-1]
    return (
        path.startswith("tests/")
        or name.startswith("test_")
        or name.endswith("_test.py")
    )


def _test_target_candidates(test_path: str) -> list[str]:
    """テストファイルからテスト対象モジュールの候補パスを列挙する.

    ``tests/foo/test_bar.py`` から ``foo/bar.py`` / ``src/foo/bar.py``、
    ``tests/test_foo.py`` から ``foo.py`` / ``src/foo.py`` を生成する。
    vendored パッケージ配下 (``ame_ai_review_system/``) に実体がある場合は
    ``<pkg>/<rel>`` も候補に加える。
    """
    if not _is_test_file(test_path):
        return []
    if not test_path.endswith(".py"):
        return []
    rel = test_path.removeprefix("tests/")
    if "/test_" in rel:
        rel = rel.replace("/test_", "/", 1)
    elif rel.startswith("test_"):
        rel = rel[len("test_") :]
    elif rel.endswith("_test.py"):
        rel = rel[: -len("_test.py")] + ".py"
    candidates = [rel, f"src/{rel}"]
    pkg_rel = review_config.package_dir_rel()
    if pkg_rel and not rel.startswith(pkg_rel):
        candidates.append(f"{pkg_rel}/{rel}")
    return candidates


def _test_target_diff(staged_files: list[str]) -> str:
    """テスト対象モジュールの実装コンテキスト (HEAD 時点の内容) を返す.

    ステージがテストファイルのみのときに、レビュアーが「実装は対応しているか」を
    繰り返し確認できないよう、テスト対象モジュールの現状を提示する (Issue #55 B1)。
    """
    if not review_config.config_bool(
        review_config.load_config(),
        "include_test_target_diff",
        default=False,
    ):
        return ""
    if not all(_is_test_file(f) for f in staged_files):
        return ""
    seen: set[str] = set()
    contents: list[str] = []
    for staged in staged_files:
        for cand in _test_target_candidates(staged):
            if cand in seen:
                continue
            seen.add(cand)
            if not precommit_state.run_git(["ls-files", "--", cand]).strip():
                continue
            content = precommit_state.run_git(["show", f"HEAD:{cand}"]).strip()
            if content:
                contents.append(
                    f"### テスト対象モジュール: {cand}\n\n```\n"
                    + _sanitize_for_codeblock(content)
                    + "\n```",
                )
    return "\n\n".join(contents)


# Issue #55 B4: fetch の短タイムアウト。precommit_state.run_git の既定 (10s) より短くし、
# 遅い回線・オフラインでコミット全体をブロックしないようにする。
_FETCH_TIMEOUT_SECONDS = 3


def _fetch_base_ref(base_ref: str) -> None:
    """``origin/{base_ref}`` を短タイムアウトでベストエフォート fetch する.

    失敗時は警告を stderr へ出力する (従来は握り潰されてブランチ diff が
    空になったり遅延したりした。Issue #55 B4)。
    """
    try:
        result = subprocess.run(
            ["git", "fetch", "origin", base_ref, "--depth=1"],
            capture_output=True,
            text=True,
            check=False,
            timeout=_FETCH_TIMEOUT_SECONDS,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        print(
            f"[precommit-review] WARNING: git fetch origin {base_ref} timed out; "
            "using stale local ref.",
            file=sys.stderr,
        )
        return
    except (FileNotFoundError, OSError) as exc:
        print(
            f"[precommit-review] WARNING: git fetch origin {base_ref} failed: {exc}",
            file=sys.stderr,
        )
        return
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        print(
            f"[precommit-review] WARNING: git fetch origin {base_ref} failed: "
            f"{detail or 'unknown error'} (using stale local ref).",
            file=sys.stderr,
        )


def _truncate_diff(diff: str) -> str:
    config = review_config.load_config()
    return diff_truncate.truncate_diff(
        diff,
        max_lines=review_config.max_diff_lines(config),
        strategy=review_config.diff_truncation_strategy(config),
        priority_markers=[_PRIORITY_DIFF_MARKER],
        context_floor=review_config.diff_truncation_context_lines(config),
    )


# Issue #112: コードフェンス (バッククォート 3 個) のサニタイズ表示トークン。
# U+201E 等の視覚的に似た文字だと、LLM が「実ファイルに本物の文字が含まれる」と誤認し
# false positive を繰り返し投稿する。非リテラル風の明示トークンへ置換し、_build_prompt
# が注記を付与して誤認を防ぐ。``<FENCE>`` はバッククォート連続と紛れず、実コードに
# ほぼ現れないため誤認しにくい。
_FENCE_PLACEHOLDER = "<FENCE>"

# バッククォート 3 個。直接リテラルで書くと、この pre-commit 自身の差分サニタイズ
# (Issue #112) が本ソースを置換してレビュアーに誤読されるため、chr で構成する。
_FENCE_MARK = chr(96) * 3


def _sanitize_for_codeblock(text: str) -> str:
    # ファイル名/コミットメッセージ/diff にコードフェンスが含まれているとプロンプトの
    # フェンス構造が壊れるため、非リテラル風トークン (<FENCE>) へ置換する。
    # U+201E („) は視覚的に近く誤認を誘発するため使わない (Issue #112)。
    return text.replace(_FENCE_MARK, _FENCE_PLACEHOLDER)


def _build_diff(base_ref: str, staged_files: list[str]) -> str:
    # 今回の staged 差分を先に置くことで、truncation が発生しても
    # 「今回のコミット対象」が必ずレビューに含まれるようにする。
    # diff 内のバックティック (docstring の削除等) でプロンプト構造が壊れないようサニタイズ。
    parts: list[str] = []
    # Issue #37: 除外対象ディレクトリ配下の差分を除去してからサニタイズする。
    staged_diff = _sanitize_for_codeblock(
        review_config.filter_review_diff(
            precommit_state.run_git(["diff", "--cached"]).strip(),
        ),
    )
    if staged_diff:
        parts.append(
            "### ステージ済み差分 (今回のコミット対象)\n\n```diff\n"
            + staged_diff
            + "\n```",
        )
    # Issue #55 I1: スタックブランチでは origin/{base} との累積差分が過大になるため、
    # 分岐元 (upstream / fork-point) を自動解決する。
    # Issue #137: ブランチ差分はステージ済み差分と重複し reasoning 予算を圧迫するため、
    # 既定では含めない (include_branch_diff: true で従来どおり含める)。
    if review_config.include_branch_diff():
        branch_range = diff_base.diff_range(base_ref)
        branch_diff = _sanitize_for_codeblock(
            review_config.filter_review_diff(
                precommit_state.run_git(["diff", branch_range]).strip(),
            ),
        )
        if branch_diff:
            parts.append(
                f"### ブランチ差分 ({branch_range})\n\n```diff\n"
                + branch_diff
                + "\n```",
            )
    # Issue #55 B1: テストのみのステージ時にテスト対象モジュールの実装コンテキストを提示する。
    test_target = _test_target_diff(staged_files)
    if test_target:
        parts.append(
            "### テスト対象モジュール (実装コンテキスト)\n\n" + test_target,
        )
    return "\n\n".join(parts)


def _build_prompt(
    base_ref: str,
    branch: str,
    staged_files: list[str],
    diff: str,
    prompt_text: str,
) -> str:
    commit_range = diff_base.commit_range(base_ref)
    commit_log = precommit_state.run_git(
        ["log", commit_range, "--oneline"],
    ).strip()
    if not commit_log:
        commit_log = "(ブランチに commit はまだありません)"
    # ファイル名やコミットメッセージに ``` が含まれているとプロンプト構造が壊れるためサニタイズ。
    sanitized_files = "\n".join(_sanitize_for_codeblock(f) for f in staged_files)
    sanitized_log = _sanitize_for_codeblock(commit_log)
    sections = [
        prompt_text,
        "",
        "## コミット情報 (pre-commit review)",
        f"- ブランチ: {branch}",
        f"- マージ想定先: {base_ref}",
        "",
        "## ステージ済みファイル一覧",
        "```",
        sanitized_files,
        "```",
        "",
        f"## コミット一覧 ({commit_range})",
        "```",
        sanitized_log,
        "```",
        "",
        "## diff",
        # _build_diff が既に各セクションを ```diff で囲んでいるため、ここでは追加しない。
        diff,
        "",
        # Issue #112: diff/ファイル名/コミットログ中の <FENCE> はサニタイズ表示。
        # LLM が実ファイルの文字と誤認して false positive を投稿しないよう注記する。
        "## 注記: コードフェンスのサニタイズ表示",
        (
            "diff / ファイル名 / コミットログ中の `<FENCE>` は、コードフェンス"
            "（バッククォート 3 個）をプロンプト構造保護のために置換した表示です。"
            "実ファイルにコードフェンスが含まれる場合は、その旨を指摘対象にしないでください。"
        ),
    ]
    # Issue #47: 除外した vendored パッケージが参照されている場合は、存在を注記して
    # 「モジュール不存在」という誤指摘を防ぐ。
    review_config.append_reference_note(sections, staged_files, diff)
    return "\n".join(sections)


def _is_blocking(comment: dict[str, Any]) -> bool:
    # LOW/INFO 以外は unknown も含めて blocking 扱い (fail-closed)。
    severity = str(comment.get("severity", "")).upper().strip()
    return severity not in _LOW_SEVERITIES


def _decide(
    comments: list[dict[str, Any]],
    streak: int,
    total: int = 0,
    *,
    low_threshold: int = _LOW_STREAK_THRESHOLD,
    total_threshold: int | None = None,
) -> tuple[bool, int, int, str]:
    """コミット可否を判定する.

    2 つの独立した escape 機構を持つ (Issue #134, Gate 2 と対称):

    1. LOW/INFO のみが ``low_threshold`` 回連続したら PASS (固定値)。
    2. 重大度によらない総レビュー回数が ``total_threshold`` に達したら、blocking
       指摘が残っていても PASS (無限ループ回避)。

    Returns ``(allow, new_low_streak, new_total, reason)``。
    """
    if total_threshold is None:
        total_threshold = review_config.precommit_max_reviews()
    if not comments:
        return True, 0, 0, "指摘 0 件のため PASS"
    new_total = total + 1
    blocking = [c for c in comments if _is_blocking(c)]
    # 総ラウンド数のハード上限を blocking 判定より先に評価する。既定では
    # total_threshold (3) > low_threshold (2) のため LOW のみ連続は先に escape し、
    # blocking はこの上限でのみ escape する。
    if new_total >= total_threshold:
        suffix = f" (blocking 指摘 {len(blocking)} 件を許容)" if blocking else ""
        # blocking が残る場合は LOW 連続カウンタをリセットする。LOW のみの場合は他経路と
        # 同様に streak を 1 進める (「LOW ラウンドは streak を進める」不変条件を保つ)。
        escaped_streak = 0 if blocking else streak + 1
        return (
            True,
            escaped_streak,
            new_total,
            (
                f"総レビュー回数 {new_total}/{total_threshold} に達したため PASS"
                f" (無限ループ回避){suffix}"
            ),
        )
    if blocking:
        return False, 0, new_total, f"blocking 指摘 {len(blocking)} 件を検出"
    # LOW-only。streak を進めて閾値に達したら抜ける。
    new_streak = streak + 1
    if new_streak >= low_threshold:
        return (
            True,
            new_streak,
            new_total,
            f"LOW のみ連続 {new_streak} 回目のため PASS (無限ループ回避)",
        )
    return (
        False,
        new_streak,
        new_total,
        f"LOW 指摘 {len(comments)} 件 (streak {new_streak}/{low_threshold})",
    )


def _format_issue(comment: dict[str, Any]) -> str:
    severity = str(comment.get("severity", "?")).upper()
    path = comment.get("path", "?")
    line = comment.get("line", "?")
    title = comment.get("title", "")
    body = comment.get("body", "")
    return f"[{severity}] {path}:{line} {title}\n    {body}"


def _demote_stale_comments(
    comments: list[dict[str, Any]],
    prev_comment_texts: list[str],
) -> tuple[list[dict[str, Any]], bool]:
    """前回レビューと同一のコメントのみを LOW へ降格する.

    stale_detect.demote_stale (コメント単位の Jaccard stale-loop 検出) で繰り返し指摘
    だけを LOW 扱いにし、新規の CRITICAL/HIGH 指摘は降格しない (Issue #55 B2)。
    escape 条件自体は変更しない。降格が発生したかを返す。
    """
    if not prev_comment_texts:
        return comments, False
    result = stale_detect.demote_stale(
        comments,
        prev_comment_texts,
        threshold=review_config.stale_threshold(),
    )
    stale_detected = any(
        a.get("severity") != b.get("severity")
        for a, b in zip(comments, result, strict=True)
    )
    return result, stale_detected


def _run_engine(
    prompt: str,
    engine_path: pathlib.Path,
    engine_settings: dict[str, Any],
) -> tuple[int, str, str]:
    env = precommit_engine.build_env(os.environ, engine_settings)
    try:
        module_name = f"{engine_path.parent.name}.{engine_path.stem}"
        result = subprocess.run(
            [sys.executable, "-m", module_name, "--role", "review"],
            input=prompt,
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=_ENGINE_TIMEOUT_SECONDS,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return -1, "", f"engine subprocess timed out after {_ENGINE_TIMEOUT_SECONDS}s"
    except (FileNotFoundError, OSError) as exc:
        return -1, "", f"failed to spawn engine: {exc}"
    return result.returncode, result.stdout, result.stderr


def _resolve_paths() -> tuple[pathlib.Path, pathlib.Path]:
    # プロンプトはプロジェクトローカル (.ame-review/) → パッケージ同梱へ解決される。
    # engine.py は常にパッケージ配下 (モジュール名解決用)。
    return paths.prompt_path(), paths.package_dir() / "engine.py"


def _print_issues(comments: list[dict[str, Any]]) -> None:
    if not comments:
        return
    print(file=sys.stderr)
    for c in comments:
        print(_format_issue(c), file=sys.stderr)
        print(file=sys.stderr)


# Issue #55 I2: プリチェックから除外する AI フック。これらを含めると再帰や
# skip_guard の巻き込みで pre-commit run がループする。
_STATIC_CHECK_EXCLUDED_HOOKS = (
    "ai-skip-guard",
    "ai-precommit-review",
    "ai-review-state-reset",
)

# pre-commit run の非ゼロ exit のうち、コード品質指摘ではなく環境 (セットアップ) 失敗と
# 判定するマーカー。初回・オフライン時のフック環境クローン/インストール失敗を
# コード品質失敗と区別する (Issue #55 I2)。
_ENV_FAILURE_MARKERS = (
    "failed to clone",
    "an error has occurred",
    "could not resolve host",
    "getaddrinfo",
    "network is unreachable",
    "etimedout",
    "connection refused",
    "unable to access",
)


def _looks_like_env_failure(detail: str) -> bool:
    """pre-commit の出力が環境 (セットアップ) 失敗かを判定する."""
    lowered = detail.lower()
    return any(marker in lowered for marker in _ENV_FAILURE_MARKERS)


def _filtered_precommit_config(raw: dict[str, Any]) -> dict[str, Any]:
    """AI フックを除外した pre-commit config の複製を返す."""
    raw = dict(raw)
    raw_repos = raw.get("repos", [])
    if not isinstance(raw_repos, list):
        return raw
    repos_list = cast("list[dict[str, Any]]", raw_repos)
    repos: list[dict[str, Any]] = []
    for repo in repos_list:
        repo_copy = dict(repo)
        raw_hooks = repo_copy.get("hooks", [])
        if isinstance(raw_hooks, list):
            hooks = cast("list[dict[str, Any]]", raw_hooks)
            repo_copy["hooks"] = [
                hook
                for hook in hooks
                if hook.get("id") not in _STATIC_CHECK_EXCLUDED_HOOKS
            ]
        repos.append(repo_copy)
    raw["repos"] = repos
    return raw


def _run_static_checks(staged_files: list[str]) -> tuple[bool, str]:
    """プロジェクト実設定の pre-commit フックで staged ファイルを検査する.

    ruff / mypy 等を直接呼ぶと実 pre-commit フックと実行条件が乖離して誤 fail する
    ため、``pre-commit run --config`` でプロジェクトの実フックをそのまま使う
    (Issue #55 I2)。AI フックは一時 config から除外して再帰を防ぐ。

    Returns (True, "") if all checks pass or no checks are available.
    Returns (False, message) if any check fails.
    """
    if not staged_files:
        return True, ""
    # pre-commit フレームワーク実行中は実フックが既にフック順序どおり強制されているため
    # 再実行しない (全フックを毎コミット二重実行する遅延を避ける。Issue #55 I2)。
    # スクリプト単体実行時のみ circuit breaker として働く。
    if os.environ.get("PRE_COMMIT"):
        return True, ""
    precommit_bin = shutil.which("pre-commit")
    if precommit_bin is None:
        print(
            "[precommit-review] static pre-check skipped (pre-commit not found).",
            file=sys.stderr,
        )
        return True, ""

    proj_root = pathlib.Path(
        precommit_state.run_git(["rev-parse", "--show-toplevel"]).strip(),
    )
    if not proj_root.is_dir():
        proj_root = paths.project_root()
    config_path = proj_root / ".pre-commit-config.yaml"
    if not config_path.is_file():
        return True, ""

    try:
        import yaml
    except ImportError:
        print(
            "[precommit-review] static pre-check skipped (PyYAML not available).",
            file=sys.stderr,
        )
        return True, ""
    try:
        parsed: object = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(
            f"[precommit-review] static pre-check skipped (cannot parse "
            f"pre-commit config: {exc}).",
            file=sys.stderr,
        )
        return True, ""
    if not isinstance(parsed, dict):
        return True, ""
    raw = cast("dict[str, Any]", parsed)
    filtered = _filtered_precommit_config(raw)

    # mkstemp + try/finally で一時 config を管理する。
    fd, tmp_name = tempfile.mkstemp(
        prefix="precommit_static_",
        suffix=".yaml",
    )
    tmp_config = pathlib.Path(tmp_name)
    try:
        try:
            fh = os.fdopen(fd, mode="w", encoding="utf-8")
        except OSError:
            os.close(fd)
            raise
        with fh:
            yaml.safe_dump(filtered, fh, allow_unicode=True, sort_keys=False)
        try:
            result = subprocess.run(
                [
                    precommit_bin,
                    "run",
                    "--config",
                    str(tmp_config),
                    "--files",
                    *staged_files,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=_STATIC_CHECK_TIMEOUT_SECONDS,
                cwd=proj_root,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError:
            print(
                "[precommit-review] static pre-check skipped (pre-commit not found).",
                file=sys.stderr,
            )
            return True, ""
        except subprocess.TimeoutExpired:
            print(
                "[precommit-review] static pre-check timed out.",
                file=sys.stderr,
            )
            return True, ""
    finally:
        tmp_config.unlink(missing_ok=True)

    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        # Issue #55 I2: 非ゼロ returncode には「フックがコード品質を指摘」以外に
        # フック環境のクローン/インストール失敗等のセットアップ失敗も含まれる。
        # 環境失敗は code-quality 失敗と区別し、毎コミットの誤ブロックを避けて
        # スキップする (circuit breaker としてはコード品質失敗のみ fail-closed)。
        if _looks_like_env_failure(detail):
            print(
                "[precommit-review] static pre-check skipped (pre-commit env failure: "
                "hook clone/install or network).",
                file=sys.stderr,
            )
            return True, ""
        return False, f"pre-commit:\n{detail}"
    return True, ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pre-commit AI code review hook.")
    parser.add_argument(
        "--base-ref",
        default=os.environ.get("BASE_REF", "main"),
        help="比較先の ref (default: main, env: BASE_REF)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="状態ファイルを更新せず常に exit 0 (確認用)",
    )
    args = parser.parse_args(argv)

    prompt_path, engine_path = _resolve_paths()

    cfg = review_config.load_config()
    if not cfg.get("precommit_review_enabled", True):
        print(
            "[precommit-review] disabled by config (precommit_review_enabled=false).",
            file=sys.stderr,
        )
        return 0

    branch = precommit_state.current_branch()
    if not branch:
        print("[precommit-review] not in a git repo; skipping.", file=sys.stderr)
        return 0
    if branch == "HEAD":
        print("[precommit-review] detached HEAD; skipping.", file=sys.stderr)
        return 0
    if not precommit_state.is_valid_branch(branch):
        print(
            f"[precommit-review] invalid branch name {branch!r}; skipping.",
            file=sys.stderr,
        )
        return 0

    raw_staged = _staged_files()
    if not raw_staged:
        # _staged_files は --diff-filter=d で削除を除くため、削除のみのステージは
        # ここに落ちる。削除は AI レビュー対象外である旨を明示する。
        deleted = precommit_state.run_git(
            ["diff", "--cached", "--name-only", "--diff-filter=D"],
        )
        deleted_files = [line for line in deleted.splitlines() if line.strip()]
        if deleted_files:
            print(
                f"[precommit-review] {len(deleted_files)} staged deletion(s); "
                "deletions are not AI-reviewed; skipping.",
                file=sys.stderr,
            )
        else:
            print("[precommit-review] no staged changes; skipping.", file=sys.stderr)
        return 0
    # Issue #37: 移植先で vendored した ame_ai_review_system 配下はレビュー対象外
    staged_files = review_config.filter_review_targets(raw_staged)
    if not staged_files:
        rel = review_config.review_exclusion_rel() or "ame_ai_review_system"
        print(
            f"[precommit-review] {len(raw_staged)} staged file(s) under "
            f"{rel} excluded (Issue #37); skipping.",
            file=sys.stderr,
        )
        return 0

    # base_ref も LLM プロンプトに埋め込むため、branch と同基準で検証する。
    if not precommit_state.is_valid_branch(args.base_ref):
        print(
            f"[precommit-review] invalid base_ref {args.base_ref!r}; skipping.",
            file=sys.stderr,
        )
        return 0

    # 前段の静的解析 (ruff / mypy) が全て pass した場合のみ AI レビューを実行する。
    # pre-commit フレームワークが既にフック順序を保証しているが、スクリプト単体実行時や
    # 防御策としても機能する。config.json の `precommit_require_static_checks` で ON/OFF 可能。
    if cfg.get("precommit_require_static_checks", True):
        passed, detail = _run_static_checks(staged_files)
        if not passed:
            print(
                f"[precommit-review] static analysis failed; "
                "skipping AI review.\n"
                f"{detail}",
                file=sys.stderr,
            )
            return 0 if args.dry_run else 1

    # base_ref のリモート追跡ブランチをベストエフォートで fetch しておく。
    # オフライン・遅い回線で毎コミットの diff 取得が遅延しないよう短タイムアウトとし、
    # 失敗は警告のみで握り潰さない。HEAD が変化していない場合は fetch をスキップする。
    fetch_state_path = precommit_state.state_file_path()
    fetch_state = precommit_state.read_state(fetch_state_path)
    head_sha = precommit_state.run_git(["rev-parse", "HEAD"]).strip()
    if head_sha and head_sha != precommit_state.get_last_fetched_head(fetch_state):
        _fetch_base_ref(args.base_ref)
        if not args.dry_run and head_sha:
            precommit_state.set_last_fetched_head(fetch_state, head_sha)
            precommit_state.write_state(fetch_state_path, fetch_state)

    diff = _truncate_diff(_build_diff(args.base_ref, staged_files))
    if not diff.strip():
        print("[precommit-review] no diff to review; skipping.", file=sys.stderr)
        return 0

    try:
        prompt_text = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[precommit-review] cannot read prompt file: {exc}", file=sys.stderr)
        return 1

    prompt = _build_prompt(args.base_ref, branch, staged_files, diff, prompt_text)

    # config 引数を渡さず config=None で呼ぶことで、リポジトリ層の明示値はファイル設定
    # (config.json / config.user.json) から解決される (Issue #126)。
    engine_settings = precommit_engine.resolve_engine_settings()
    # Issue #40: エンジン情報 (engine/model/thinking) のバナーは
    # show_engine_info_gate1 が true のときのみ出力する (既定=表示)。
    if engine_settings.get("show_info", True):
        print(
            f"[precommit-review] running AI review on branch '{branch}' "
            f"(staged files: {len(staged_files)}; "
            f"engine={engine_settings['engine']}, "
            f"model={engine_settings['model'] or '<engine-default>'}, "
            f"thinking={engine_settings['thinking']})...",
            file=sys.stderr,
        )

    exit_code, output, engine_err = _run_engine(prompt, engine_path, engine_settings)
    if engine_err.strip():
        # エンジンスタブに API キーや内部パスが含まれる可能性があるため、
        # プレフィックスを付けて開発者端末への露出を明確にする。
        for line in engine_err.splitlines():
            print(f"[engine] {line}", file=sys.stderr)
    # fail-closed 原則だが、LLM API のレート制限や一時障害で永遠にコミットできなくなるのを
    # 避けるため、エンジン失敗は engine_failure_streak に計上し 3 回連続で escape する。
    # low_only_streak とは独立カウンタで混在を防ぐ。
    if exit_code != 0 or not output.strip():
        state_path = precommit_state.state_file_path()
        state = precommit_state.read_state(state_path)
        streak = precommit_state.get_streak(
            state,
            branch,
            key="engine_failure_streak",
        )
        new_streak = streak + 1
        if not args.dry_run:
            precommit_state.set_streak(
                state,
                branch,
                new_streak,
                key="engine_failure_streak",
            )
            precommit_state.write_state(state_path, state)
        if new_streak >= _ENGINE_FAILURE_STREAK_THRESHOLD:
            print(
                f"[precommit-review] engine failed (exit={exit_code}) but "
                f"streak {new_streak}/{_ENGINE_FAILURE_STREAK_THRESHOLD} reached; "
                "allowing commit (escape hatch).",
                file=sys.stderr,
            )
            return 0
        print(
            f"[precommit-review] engine failed (exit={exit_code}); "
            f"blocking commit (fail-closed). streak {new_streak}/"
            f"{_ENGINE_FAILURE_STREAK_THRESHOLD} — 連続で失敗すると escape します。",
            file=sys.stderr,
        )
        return 0 if args.dry_run else 1

    # payload.parse_review_json はファイルパスを要求するため一時ファイルへ。
    # mkstemp + try/finally で「生成から削除まで」を一括管理し、write 失敗時のリークを防ぐ。
    review_fd, review_name = tempfile.mkstemp(suffix=".json")
    review_tmp = pathlib.Path(review_name)
    try:
        try:
            fh = os.fdopen(review_fd, mode="w", encoding="utf-8")
        except OSError:
            os.close(review_fd)
            raise
        with fh:
            fh.write(output)
        review, is_fallback = payload.parse_review_json_with_flag(
            str(review_tmp),
            repair=lambda broken: payload.repair_review_json(
                broken,
                lambda p: payload.engine_output_text(
                    _run_engine(
                        p,
                        engine_path,
                        review_config.apply_repair_model(engine_settings),
                    ),
                ),
            ),
        )
    finally:
        review_tmp.unlink(missing_ok=True)

    # 不正 JSON で parse が fallback した場合、フォールバックは comments=[]
    # となり PASS 扱いになる。これは fail-closed ポリシーに違反するためブロックする。
    if is_fallback:
        print(
            "[precommit-review] engine output could not be parsed as JSON; "
            "blocking commit (fail-closed).",
            file=sys.stderr,
        )
        return 1

    # comments キーが欠損 / 非 list の場合も不正出力としてブロックする (fail-closed)。
    if "comments" not in review or not isinstance(review.get("comments"), list):
        print(
            "[precommit-review] engine output has invalid 'comments' field; "
            "blocking commit (fail-closed).",
            file=sys.stderr,
        )
        return 1
    filtered_comments: list[dict[str, Any]] = [
        c for c in review["comments"] if isinstance(c, dict)
    ]

    state_path = precommit_state.state_file_path()
    state = precommit_state.read_state(state_path)
    # エンジンが正常応答したので engine_failure_streak をリセットする。
    # これにより「連続失敗」の語義が保たれる (失敗 → 成功 → 失敗 で streak は 1 に戻る)。
    precommit_state.set_streak(state, branch, 0, key="engine_failure_streak")
    streak = precommit_state.get_streak(state, branch)
    total = precommit_state.get_streak(state, branch, key="total_review_count")

    # Issue #55 B2: 前回レビューと同一のコメント (コメント単位の stale-loop 検出) のみを
    # LOW へ降格し、severity の揺れ (MIDDLE → LOW → MIDDLE) で streak escape が進まない
    # 問題を解消する。新規指摘は降格しない。escape 条件自体は変更しない。
    recent_reviews = precommit_state.get_recent_reviews(state, branch)
    filtered_comments, stale_detected = _demote_stale_comments(
        filtered_comments,
        recent_reviews,
    )
    if stale_detected:
        print(
            "[precommit-review] stale-loop detected; matching comments demoted to LOW.",
            file=sys.stderr,
        )

    total_review_limit = review_config.precommit_max_reviews()
    allow, new_streak, new_total, reason = _decide(
        filtered_comments,
        streak,
        total,
        total_threshold=total_review_limit,
    )

    print(f"[precommit-review] {reason}", file=sys.stderr)
    # Issue #134: 総ラウンド上限で blocking 指摘を許容して escape した場合は、
    # その旨を明示的に警告する (Gate 2 の通知コメント相当)。
    if allow and filtered_comments and any(_is_blocking(c) for c in filtered_comments):
        print(
            "[precommit-review] WARNING: 総レビュー回数上限 "
            f"({new_total}/{total_review_limit}) に達したため、blocking 指摘が"
            "残っていますがコミットを許可します。指摘への対応状況を確認してください。",
            file=sys.stderr,
        )
    summary = str(review.get("summary", "")).strip()
    if summary:
        print(f"[precommit-review] summary: {summary}", file=sys.stderr)
    _print_issues(filtered_comments)

    if args.dry_run:
        print(
            f"[precommit-review] dry-run: would set streak={new_streak}, "
            f"total={new_total}, allow={allow}",
            file=sys.stderr,
        )
        return 0

    precommit_state.set_streak(state, branch, new_streak)
    precommit_state.set_streak(state, branch, new_total, key="total_review_count")
    # 次回の stale-loop 判定用に今回のレビューをコメント単位で保持する。
    current_texts = [stale_detect.comment_text(c) for c in filtered_comments]
    if current_texts:
        precommit_state.set_recent_reviews(state, branch, current_texts)
    precommit_state.write_state(state_path, state)

    if allow:
        print("[precommit-review] commit allowed.", file=sys.stderr)
        return 0
    remaining_low = _LOW_STREAK_THRESHOLD - new_streak
    remaining_total = total_review_limit - new_total
    print(
        "[precommit-review] commit BLOCKED. 修正して再 add するか、"
        f"LOW 指摘のみが続く場合はあと {remaining_low} 回 (streak)、"
        f"重大度によらずあと {remaining_total} 回 (総ラウンド上限) で抜けられます。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
