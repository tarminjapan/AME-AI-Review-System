"""``ame-ai-reviewer init`` サブコマンド: 配布先に必要なファイルを生成する.

pip インストールされたパッケージのテンプレート (``templates/``) を基に、
プロジェクトローカルへ以下を配置する:

- ``.ame-review/config.json`` / ``review_prompt.txt`` (プロジェクト固有設定)
- ``.pre-commit-config.yaml`` (preset 選択式の静的解析 + AI レビュー)
- ``.github/workflows/review_command.yml`` / ``review_reply.yml``
  (reusable workflow を呼ぶ薄いラッパ)

idempotent: 既存ファイルは上書きしない。``--force`` で上書きする。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

from . import paths

if TYPE_CHECKING:
    import argparse
    from pathlib import Path

# preset 名 → templates/precommit/ のファイル名。
_PRESETS: dict[str, str] = {
    "full": "full.yaml",
    "minimal": "minimal.yaml",
    "python": "python.yaml",
    "text": "text.yaml",
}

# Gate 1 の AI フック entry: に埋め込む Python インタープリタのプレースホルダ。
# PEP 668 (externally-managed) 環境ではシステム Python への ``pip install --user`` が
# ブロックされるため、init を実行中のインタープリタ (venv/uv/pipx) を埋め込む (Issue #66)。
_PYTHON_BIN_PLACEHOLDER = "__PYTHON_BIN__"

# .ame-review/ へ配置する既定ファイル (存在するテンプレートのみ)。
_AME_REVIEW_FILES = (
    "config.json",
    "review_prompt.txt",
)

# ワークフローテンプレート → 生成先ファイル名。
_WORKFLOW_FILES = (
    ("review-command-wrapper.yml", "review_command.yml"),
    ("review-reply-wrapper.yml", "review_reply.yml"),
)


def _templates_dir() -> Path:
    return paths.package_dir() / "templates"


def _resolve_python_bin(args: argparse.Namespace) -> str:
    """Gate 1 フックへ埋め込む Python インタープリタのパスを解決する (Issue #66).

    優先順位: ``--python`` フラグ → ``AME_INIT_PYTHON`` 環境変数 → ``sys.executable``。
    PEP 668 環境では ``sys.executable`` が venv/uv/pipx のインタープリタを指すため、
    そこへ ``ame_ai_review_system`` がインストールされていればフックが動作する。
    """
    explicit = getattr(args, "python", None)
    if explicit:
        return str(explicit)
    env_python = os.environ.get("AME_INIT_PYTHON")
    if env_python:
        return env_python
    return sys.executable


def _verify_importable(python_bin: str) -> bool:
    """``python_bin`` で ``ame_ai_review_system`` が import 可能か検証する."""
    try:
        result = subprocess.run(
            [python_bin, "-c", "import ame_ai_review_system"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _print_import_help(python_bin: str) -> None:
    """``ame_ai_review_system`` が import できない場合の修正手順を表示する (Issue #66)."""
    print(
        "WARNING: ame_ai_review_system が指定の Python で import できません。\n"
        f"  Python: {python_bin}\n"
        "  Gate 1 (pre-commit AI フック) が動作しません。以下のいずれかで導入してください:\n"
        "    1. venv:  python -m venv .venv && . .venv/bin/activate && pip install <wheel>\n"
        "    2. uv:    uv tool install <wheel>\n"
        "    3. pipx:  pipx install <wheel>\n"
        "  その後、ame-ai-reviewer init --python <そのPythonのパス> を再実行してください。",
        file=sys.stderr,
    )


def _write(dst: Path, content: str, *, force: bool) -> bool:
    if dst.exists() and not force:
        print(f"  skip (exists): {dst}")
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content, encoding="utf-8")
    print(f"  write: {dst}")
    return True


def _copy_template(src: Path, dst: Path, *, force: bool) -> bool:
    if dst.exists() and not force:
        print(f"  skip (exists): {dst}")
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  write: {dst}")
    return True


def cmd_init(args: argparse.Namespace) -> int:
    root = paths.project_root()
    print(f"Initializing AME AI Review System in {root}")

    # .ame-review/ へ既定ファイルを配置 (ユーザー固有設定は config.user.json で上書き)。
    ame_dir = paths.ame_review_dir()
    ame_dir.mkdir(parents=True, exist_ok=True)
    for name in _AME_REVIEW_FILES:
        src = _templates_dir() / "ame-review" / name
        if not src.exists():
            continue
        _copy_template(src, ame_dir / name, force=args.force)

    # .pre-commit-config.yaml を preset から生成。
    preset_file = _PRESETS.get(args.preset, _PRESETS["full"])
    src = _templates_dir() / "precommit" / preset_file
    if not src.exists():
        print(f"ERROR: preset template not found: {src}", file=sys.stderr)
        return 1
    # Issue #66: Gate 1 フックの entry: に実インタープリタパスを埋め込む。
    python_bin = _resolve_python_bin(args)
    if " " in python_bin:
        print(
            "WARNING: Python パスに空白が含まれます。pre-commit の entry: は shlex "
            "分割するため空白入りパスは正常に起動できません。空白を含まないパス "
            "(シンボリックリンク等) を --python で指定してください (Issue #66)。",
            file=sys.stderr,
        )
    import_ok = _verify_importable(python_bin)
    if not import_ok:
        _print_import_help(python_bin)
        # 明示的な --python 指定で import 不可なら、壊れた Gate 1 設定を書き出さず
        # fail fast する。自動解決 (env/sys.executable) の場合は静的解析設定だけでも
        # 有用なため警告しつつ書き出す (Issue #66)。
        if args.python:
            return 1
    preset_content = src.read_text(encoding="utf-8").replace(
        _PYTHON_BIN_PLACEHOLDER,
        python_bin,
    )
    _write(root / ".pre-commit-config.yaml", preset_content, force=args.force)

    # CI ラッパワークフローを生成 (reusable workflow 呼び出し)。
    if not args.no_workflow:
        if not args.ref:
            print(
                "ERROR: --ref is required unless --no-workflow "
                "(use a release tag, e.g. --ref v1.0.0)",
                file=sys.stderr,
            )
            return 1
        workflows_dir = root / ".github" / "workflows"
        for tmpl_name, out_name in _WORKFLOW_FILES:
            src = _templates_dir() / "workflow" / tmpl_name
            if not src.exists():
                print(f"ERROR: workflow template not found: {src}", file=sys.stderr)
                return 1
            content = src.read_text(encoding="utf-8").replace("__REF__", args.ref)
            _write(workflows_dir / out_name, content, force=args.force)

    # engines-ts の展開 + npm install (オプション)。
    if args.with_engines:
        print("Installing TypeScript SDK sidecar (engines-ts)...")
        try:
            dst = paths.ensure_engines_ts()
        except SystemExit as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"  OK: {dst}")

    print("Done. Next steps:")
    print("  1. レビュー用 GitHub App をリポジトリにインストールし Secrets を設定する")
    print("  2. 必要な静的解析ツールを導入する (preset は .pre-commit-config.yaml)")
    print("  3. pre-commit フックを登録する: pre-commit install")
    return 0
