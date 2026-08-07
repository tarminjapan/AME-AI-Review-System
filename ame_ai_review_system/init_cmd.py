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

import shutil
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
    "ts": "ts.yaml",
}

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


def _resolve_preset(preset: str, root: Path) -> str:
    """Preset 名を解決する (Issue #69).

    ``auto`` (既定) のとき ``package.json`` があれば Node/TS 向き ``ts`` を選び、
    無ければ ``full`` を選ぶ。明示指定された preset はそのまま返す。
    """
    if preset != "auto":
        return preset
    if (root / "package.json").exists():
        print("  package.json detected; preset = ts")
        return "ts"
    print("  no package.json; preset = full")
    return "full"


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
    preset_name = _resolve_preset(args.preset, root)
    preset_file = _PRESETS.get(preset_name, _PRESETS["full"])
    src = _templates_dir() / "precommit" / preset_file
    if not src.exists():
        print(f"ERROR: preset template not found: {src}", file=sys.stderr)
        return 1
    _copy_template(src, root / ".pre-commit-config.yaml", force=args.force)

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
