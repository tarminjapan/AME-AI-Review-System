"""Review system configuration loader and slash-command detection.

サブコマンド:
  get <key>                 ``config.json`` から値を読み取り stdout へ出力する。
                            ファイルやキーが存在しない場合は組み込みデフォルトを使う。
  is-review-command <body>  コメント本文がレビュー要求コマンド
                            (``/request-review`` / ``/review``) かを判定し
                            ``true`` / ``false`` を stdout へ出力する。

設定ファイルのパスは環境変数 ``AME_REVIEW_CONFIG`` で上書き可能。
ユーザー固有の上書きは ``config.user.json``（環境変数 ``AME_REVIEW_USER_CONFIG`` でパス変更可能）に記述する。
``config.user.json`` は Git 管理対象外であり、存在しない場合は無視される。
"""

from __future__ import annotations

import ast
import contextlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

from . import paths

_DEFAULTS: dict[str, Any] = {
    "precommit_review_enabled": True,
    "precommit_require_static_checks": True,
    "pr_review_require_static_checks": True,
    "ai_review_enforce_no_skip": True,
    # Issue #37: 移植先で vendored した ame_ai_review_system 配下は既定でレビュー対象外。
    "review_include_package_dir": False,
    # Issue #55 B1: テストのみのステージ時にテスト対象モジュールの実装コンテキストを
    # diff へ追加する (既定 false。プロンプトのガードレールが主対策)。
    "include_test_target_diff": False,
    "precommit_engine": "auto",
    "precommit_model": None,
    "precommit_thinking": None,
    "precommit_review_budget_usd": None,
    # Issue #40: レビューエンジン情報 (engine/model/thinking) の表示トグル (既定=表示)。
    "show_engine_info_gate1": True,
    "show_engine_info_gate2": True,
    # Issue #37: 壊れたレビュー JSON を修復する際に使うモデル (省略時は本体と同じ)。
    "review_repair_model": None,
    # Issue #65: 壊れたレビュー JSON を LLM で修復する最大試行回数。パース失敗で
    # ラウンド全体が不成立になるのを防ぐため、既定を従来の 2 から 3 へ引き上げる。
    "review_repair_attempts": 3,
    "engine": "claude",
    # Issue #55 B3/I3: model 既定を None 化し、非 claude エンジンはサーバー既定へ委ねる。
    # claude のみ engine.py 側で sonnet 既定を維持する (後方互換)。
    "model": None,
    "review_model": None,
    "reply_model": "haiku",
    "thinking": "high",
    "review_thinking": "high",
    "reply_thinking": "low",
    "review_budget_usd": 2.00,
    "reply_budget_usd": 0.20,
    # Issue #62: 差分切り捨て上限。これを超えると priority/front 戦略で切り詰める。
    "max_diff_lines": 4000,
    # Issue #62: 切り詰め戦略。"priority" は優先セクション(ステージ済み差分等)を全行保持し、
    # 残予算をコンテキスト側(ブランチ差分等)の後方ファイルから確保する。"front" は従来動作。
    "diff_truncation_strategy": "priority",
    # Issue #62: priority 戦略でコンテキスト側に最低限残す行数。markers ありの
    # 優先セクションモードでは優先セクションが大きい際にこの行数をコンテキスト末尾へ
    # 保証し、markers なしの head+tail モードでは末尾長となる。後方ファイルの不可視化を防ぐ。
    "diff_truncation_context_lines": 800,
}

_REVIEW_COMMANDS = ("/request-review", "/review")

_MIN_ARGS = 2


def _config_path() -> Path:
    override = os.environ.get("AME_REVIEW_CONFIG")
    if override:
        return Path(override)
    return paths.config_path()


def _user_config_path() -> Path:
    override = os.environ.get("AME_REVIEW_USER_CONFIG")
    if override:
        return Path(override)
    return paths.user_config_path()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return cast("dict[str, Any]", data) if isinstance(data, dict) else None


def load_config() -> dict[str, Any]:
    config: dict[str, Any] = dict(_DEFAULTS)
    data: dict[str, object] | None = _read_json(_config_path())
    if data is not None:
        config.update(data)
    user_data = _read_json(_user_config_path())
    if user_data is not None:
        config.update(user_data)
    return config


def config_bool(
    config: Mapping[str, Any],
    key: str,
    *,
    default: bool = True,
) -> bool:
    """Config の真偽値キーを厳密に解釈する.

    JSON の bool だけでなく、手編集で ``"false"`` のような文字列が書かれた場合も
    正しく判定する (Issue #40 の表示トグル等)。値が存在しない場合は ``default``。
    """
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if not value.strip():
            return default
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def user_overrides() -> dict[str, Any]:
    """Return keys explicitly set in config.json or config.user.json (user wins)."""
    overrides: dict[str, Any] = {}
    data: dict[str, object] | None = _read_json(_config_path())
    if data is not None:
        overrides.update(data)
    user_data = _read_json(_user_config_path())
    if user_data is not None:
        overrides.update(user_data)
    return overrides


# ============================================================================
# Issue #37: vendored ame_ai_review_system 配下のレビュー除外
# ============================================================================


def package_dir_rel() -> str | None:
    """プロジェクトルート相対の vendored パッケージディレクトリパス (POSIX) を返す.

    パッケージがリポジトリ外 (pip インストール等) にある場合は ``None``。
    例: ``ame_ai_review_system`` / ``vendor/ame_ai_review_system``。
    """
    try:
        rel = (
            paths
            .package_dir()
            .resolve()
            .relative_to(
                paths.project_root().resolve(),
            )
        )
    except ValueError:
        return None
    return rel.as_posix() if rel.parts else None


def review_exclusion_rel() -> str | None:
    """レビューから除外すべきパッケージ相対パスを返す.

    ``review_include_package_dir: true`` のときや、パッケージがリポジトリ外に
    ある場合は ``None`` (除外なし)。
    """
    if load_config().get("review_include_package_dir", False):
        return None
    return package_dir_rel()


# ============================================================================
# Issue #62: 差分切り捨て設定
# ============================================================================


def max_diff_lines(config: Mapping[str, Any] | None = None) -> int:
    """差分切り捨て上限行数を返す (既定 4000)."""
    cfg = config if config is not None else load_config()
    raw = cfg.get("max_diff_lines", _DEFAULTS["max_diff_lines"])
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return int(_DEFAULTS["max_diff_lines"])
    return value if value > 0 else int(_DEFAULTS["max_diff_lines"])


def diff_truncation_strategy(config: Mapping[str, Any] | None = None) -> str:
    """切り捨て戦略 (``"priority"`` / ``"front"``) を返す (既定 ``priority``)."""
    cfg = config if config is not None else load_config()
    raw = str(
        cfg.get("diff_truncation_strategy", _DEFAULTS["diff_truncation_strategy"])
    )
    normalized = raw.strip().lower()
    return normalized if normalized in {"priority", "front"} else "priority"


def diff_truncation_context_lines(config: Mapping[str, Any] | None = None) -> int:
    """Priority 戦略でコンテキスト側に最低限残す行数を返す (既定 800).

    markers ありの優先セクションモードでは優先セクションが大きい際にこの行数を
    コンテキスト末尾へ保証する。markers なしの head+tail モードでは末尾長となる。
    """
    cfg = config if config is not None else load_config()
    raw = cfg.get(
        "diff_truncation_context_lines", _DEFAULTS["diff_truncation_context_lines"]
    )
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return int(_DEFAULTS["diff_truncation_context_lines"])
    return value if value >= 0 else int(_DEFAULTS["diff_truncation_context_lines"])


def apply_repair_model(settings: dict[str, Any]) -> dict[str, Any]:
    """修復専用モデル ``review_repair_model`` を設定へ適用する.

    省略時は本体と同じモデルを使うため ``settings`` をそのまま返す。壊れやすい
    弱いモデル (deepseek-v4-flash 等) を JSON 修復には使わないための共通処理。
    """
    repair_model = load_config().get("review_repair_model")
    if repair_model:
        return {**settings, "model": repair_model}
    return settings


def max_repair_attempts(config: Mapping[str, Any] | None = None) -> int:
    """壊れたレビュー JSON の LLM 修復最大試行回数を返す (既定 3, Issue #65)."""
    cfg = config if config is not None else load_config()
    raw = cfg.get("review_repair_attempts", _DEFAULTS["review_repair_attempts"])
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return int(_DEFAULTS["review_repair_attempts"])
    return value if value > 0 else int(_DEFAULTS["review_repair_attempts"])


def filter_review_targets(files: list[str]) -> list[str]:
    """``files`` から除外対象パッケージ配下のパスを取り除く."""
    rel = review_exclusion_rel()
    if rel is None:
        return list(files)
    return [f for f in files if not _is_path_under(f, rel)]


def filter_review_diff(diff_text: str) -> str:
    """``diff`` から除外対象パッケージ配下のファイルセクションを取り除く.

    セクション内の全パスが除外対象配下にある場合のみ破棄する。リネーム等で
    ``a/src/old.py`` → ``b/ame_ai_review_system/new.py`` のように除外ディレクトリを
    跨ぐ場合は、非除外側の変更 (un-vendoring 等) をレビューから消さないよう保持する。
    """
    rel = review_exclusion_rel()
    if rel is None or not diff_text:
        return diff_text
    kept: list[str] = []
    for section in _split_diff_sections(diff_text):
        paths_in_section = _section_paths(section)
        if paths_in_section and all(_is_path_under(p, rel) for p in paths_in_section):
            continue
        kept.append("\n".join(section))
    return "\n".join(kept)


def _is_path_under(path: str, rel: str) -> bool:
    return path == rel or path.startswith(rel + "/")


# ============================================================================
# Issue #47: 除外した vendored パッケージが参照されている場合のプロンプト注記
# ============================================================================


def excluded_package_reference_note(files: list[str], diff_text: str) -> str:
    """Review 対象から除外した vendored パッケージの参照注記を返す.

    ``review_include_package_dir: false`` (既定) で vendored パッケージ配下が diff から
    除外されると、モデルが「diff に無い = モジュール不存在」と誤判定し、HIGH/MIDDLE の
    誤指摘でコミットがブロックされる (Issue #47)。

    そこで、除外対象パッケージが変更ファイルや diff から参照されており、かつ参照先
    (サブモジュール/パス) の実体がリポジトリに存在する場合のみ、プロンプトへ
    「vendored 済み・レビュー対象外」である旨の注記を返す。該当しない場合は空文字を返す。

    - パッケージがリポジトリ外 (pip 等) にある場合: 除外対象ではないため空文字。
    - ``review_include_package_dir: true`` の場合: 除外していないため空文字。
    - 参照が無い、または実体が存在しない場合: 注記不要のため空文字。
    - 参照されたサブモジュールの 1 つでも実在しない場合: typo 等の実バグを見逃さないよう
      注記しない (モデルが従来どおり指摘できる)。
    """
    rel = review_exclusion_rel()
    if rel is None:
        return ""
    pkg_name = rel.split("/")[-1]
    texts: list[str] = [diff_text, *files]
    if not any(_text_references_package(pkg_name, t) for t in texts):
        return ""
    subpaths: set[str] = set()
    for t in texts:
        subpaths |= _referenced_subpaths(pkg_name, t)
    # 参照先サブパスがある場合はそちらを検証する。ない場合 (単体のパッケージ名参照) は
    # パッケージディレクトリの存在を検証する。
    if subpaths:
        if not _package_subpaths_exist(rel, subpaths):
            return ""
    elif not _package_exists_in_repo(rel):
        return ""
    return (
        "\n## 注記: vendored パッケージの参照 (レビュー対象外)\n"
        f"- `{rel}/` はレビュー対象外のため diff には含まれていませんが、リポジトリに"
        "存在します (vendored 済み)。\n"
        f"- 差分やコメントで参照されている `{pkg_name}.` / `{pkg_name}/` などの"
        f"モジュール・パスは実在するため、`{pkg_name}` に関する「モジュールが存在しない」"
        "という指摘は行わないでください。\n"
    )


def append_reference_note(lines: list[str], files: list[str], diff_text: str) -> None:
    """プロンプトの行リストへ vendored パッケージ参照注記を追記する (Issue #47).

    注記不要 (除外対象外・参照なし・実体なし) の場合は何も追加しない。
    """
    note = excluded_package_reference_note(files, diff_text)
    if note:
        lines.append(note)


def _text_references_package(pkg_name: str, text: str) -> bool:
    """``text`` がパッケージ名 (``ame_ai_review_system`` 等) を参照しているか判定する."""
    if not text:
        return False
    return re.search(r"\b" + re.escape(pkg_name) + r"\b", text) is not None


def _referenced_subpaths(pkg_name: str, text: str) -> set[str]:
    """``text`` からパッケージ名に続く参照サブパス (モジュール名/パス) を抽出する.

    ``ame_ai_review_system.skip_guard`` から ``skip_guard``、
    ``ame_ai_review_system/engines/ts`` から ``engines/ts`` を取り出す。
    参照先が無い (単体の ``ame_ai_review_system`` 等) 場合は空集合を返す。
    ドット連鎖の末尾は属性アクセス (``main.run()`` 等) の可能性があるため除去せず、
    検証側でプレフィックスへ縮めて確認する。
    """
    if not text:
        return set()
    pattern = re.compile(r"\b" + re.escape(pkg_name) + r"[./]([A-Za-z0-9_./-]+)")
    return {
        m.group(1).rstrip(".,;:)]}>")
        for m in pattern.finditer(text)
        if m.group(1).rstrip(".,;:)]}>")
    }


_exists_cache: dict[tuple[str, str], bool] = {}


def _package_exists_in_repo(rel: str) -> bool:
    """除外対象パッケージがリポジトリに存在するか判定する.

    ``git ls-files --error-unmatch`` で追跡ファイルの存在を機械的に検証する (Issue #47)。
    git が利用できない環境では、作業ツリーのディレクトリ存在をフォールバックに使う。
    検証結果は ``(project_root, rel)`` をキーにプロセス内キャッシュする。
    """
    key = (str(paths.project_root()), rel)
    if key in _exists_cache:
        return _exists_cache[key]
    exists = _package_exists_check(rel)
    _exists_cache[key] = exists
    return exists


def _package_exists_check(rel: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel.rstrip("/") + "/"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            cwd=paths.project_root(),
        )
        if result.returncode == 0:
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    return (paths.project_root() / rel).is_dir()


def _package_subpaths_exist(rel: str, subpaths: Iterable[str]) -> bool:
    """参照された全サブパスが実在する場合のみ ``True`` を返す.

    1 つでも欠落があれば ``False`` (typo / バージョン差の可能性が高い)。
    ``git ls-files`` は全サブパスの候補パスをまとめて 1 回起動する。
    """
    subpaths = sorted(set(subpaths))
    if not subpaths:
        return True
    candidates = {
        subpath: _package_subpath_candidates(rel, subpath) for subpath in subpaths
    }
    matched = _package_matched_files(
        [c for cs in candidates.values() for c in cs],
    )
    root = paths.project_root()
    for cs in candidates.values():
        if any(_candidate_matched(c, matched) for c in cs):
            continue
        if not any((root / c).exists() for c in cs):
            return False
    return True


def _package_subpath_candidates(rel: str, subpath: str) -> list[str]:
    """``subpath`` の実在検証に使う候補パスを列挙する.

    ``main.run`` のようなドット連鎖はモジュール ``main`` の属性アクセスである可能性が
    高いため、末尾セグメントを順に取り除いたプレフィックスも候補に含める
    (``main.run`` → ``rel/main/run.py`` と ``rel/main.py`` の両方)。
    """
    parts = subpath.replace(".", "/").split("/")
    candidates: list[str] = []
    for i in range(len(parts), 0, -1):
        prefix = "/".join(parts[:i])
        candidates.extend(
            [
                f"{rel}/{prefix}.py",
                f"{rel}/{prefix}.pyi",
                f"{rel}/{prefix}/",
                f"{rel}/{prefix}",
            ],
        )
    return candidates


def _package_matched_files(candidates: list[str]) -> set[str]:
    """``git ls-files`` で候補パス群と一致する追跡ファイルの集合を返す."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--", *candidates],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            cwd=paths.project_root(),
        )
        if result.returncode == 0:
            return {line.strip() for line in result.stdout.splitlines() if line.strip()}
    except (OSError, subprocess.SubprocessError):
        pass
    return set()


def _candidate_matched(candidate: str, matched: set[str]) -> bool:
    if candidate in matched:
        return True
    if candidate.endswith("/"):
        return any(path.startswith(candidate) for path in matched)
    return False


def _split_diff_sections(diff_text: str) -> list[list[str]]:
    """``diff --git`` ヘッダ行で diff をファイル単位のセクションへ分割する."""
    lines = diff_text.splitlines()
    sections: list[list[str]] = []
    current: list[str] = []
    for i, line in enumerate(lines):
        if line.startswith("diff --git ") and _looks_like_diff_header(lines, i):
            if current:
                sections.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append(current)
    return sections


# ヘッダ直後に現れるファイル境界の目印。差分の内容行 (追加/削除) は必ず
# ``+`` / ``-`` / スペースで始まるため、この判定で誤分割しない。
_DIFF_HEADER_FOLLOWERS = (
    "index ",
    "new file mode ",
    "deleted file mode ",
    "old mode ",
    "new mode ",
    "similarity index ",
    "dissimilarity index ",
    "rename from ",
    "rename to ",
    "copy from ",
    "copy to ",
    "--- ",
    "+++ ",
)


def _looks_like_diff_header(lines: list[str], i: int) -> bool:
    """``diff --git`` 行がファイル境界か (直後の数行にヘッダ対が続くか) 判定する."""
    for j in range(i + 1, min(i + 4, len(lines))):
        if lines[j].startswith(_DIFF_HEADER_FOLLOWERS):
            return True
    return False


# ``diff --git a/foo b/foo`` ヘッダ内のパストークン。空白を含むパスは git が
# 全体を ``"a/path with space"`` のようにダブルクォートで引用するため、
# 引用符で括られたトークンと通常トークンの両方を許容する。
_HEADER_TOKEN_RE = re.compile(r"(\"(?:a/|b/)[^\"]*\"|(?:a/|b/)[^ \t]+)")


def _unquote_path(raw: str) -> str:
    # git は特殊文字を含むパスを C スタイル引用符で出力する。
    if raw.startswith('"') and raw.endswith('"'):
        with contextlib.suppress(SyntaxError, ValueError):
            raw = cast("str", ast.literal_eval(raw))
    return raw


def _strip_path_prefix(raw: str) -> str:
    # ``a/`` / ``b/`` プレフィックスを除去する。
    if raw.startswith(("a/", "b/")):
        return raw[2:]
    return raw


def _section_paths(section: list[str]) -> list[str]:
    """セクションからリポジトリ相対パスを抽出する.

    ``diff --git`` ヘッダ行 (バイナリ差分・モード変更のみの差分にも存在) と
    ``--- a/..`` / ``+++ b/..`` 行の両方から抽出する。追加・削除の
    ``/dev/null`` 疑似パスは実ファイルでないため除外する。
    """
    paths_in_section: list[str] = []
    for line in section:
        if line.startswith("diff --git "):
            rest = line[len("diff --git ") :]
            paths_in_section.extend(
                _strip_path_prefix(_unquote_path(m.group(1)))
                for m in _HEADER_TOKEN_RE.finditer(rest)
            )
        elif line.startswith(("--- ", "+++ ")):
            raw = _strip_path_prefix(_unquote_path(line[4:].strip()))
            if raw not in {"/dev/null", "null"}:
                paths_in_section.append(raw)
    return paths_in_section


def is_review_command(body: str) -> bool:
    stripped = body.strip()
    if not stripped:
        return False
    first_line = stripped.splitlines()[0].strip()
    return any(
        first_line == cmd or first_line.startswith(cmd + " ")
        for cmd in _REVIEW_COMMANDS
    )


def get_ts_checks(ts_files: list[str]) -> list[tuple[str, list[str]]]:
    """Return command lists for TypeScript compiler and ESLint checks."""
    if not ts_files:
        return []
    checks: list[tuple[str, list[str]]] = []
    # tsc は tsconfig_path が明示指定された場合のみ実行する。
    # ルート tsconfig.json はしばしばソリューション参照型で広すぎ、無関係な既存エラーが
    # 回帰として表面化するため自動検出しない (専用の tsc フックで別途担保すること)。
    tsconfig = load_config().get("tsconfig_path")
    if tsconfig:
        checks.append(
            (
                "tsc",
                [
                    "./node_modules/.bin/tsc",
                    "--noEmit",
                    "-p",
                    str(tsconfig),
                ],
            ),
        )
    checks.append(
        (
            "eslint",
            [
                "./node_modules/.bin/eslint",
                "--max-warnings=0",
                "--no-warn-ignored",
                *ts_files,
            ],
        ),
    )
    return checks


def _emit_value(value: Any) -> None:
    if isinstance(value, bool):
        print("true" if value else "false")
    elif value is None:
        print()
    else:
        print(value)


def _cmd_get(args: list[str]) -> int:
    key = args[0] if args else ""
    _emit_value(load_config().get(key, _DEFAULTS.get(key)))
    return 0


def _cmd_is_review_command(args: list[str]) -> int:
    body = args[0] if args else ""
    print("true" if is_review_command(body) else "false")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < _MIN_ARGS:
        print(
            "Usage: review_config.py get <key> | is-review-command <body>",
            file=sys.stderr,
        )
        return 2
    cmd = argv[1]
    rest = argv[2:]
    if cmd == "get":
        return _cmd_get(rest)
    if cmd == "is-review-command":
        return _cmd_is_review_command(rest)
    print(f"Unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
