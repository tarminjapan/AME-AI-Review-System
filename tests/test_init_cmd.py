# pyright: basic
from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from ame_ai_review_system import init_cmd


def _make_args(**kwargs: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "preset": "full",
        "ref": "main",
        "no_workflow": False,
        "with_engines": False,
        "force": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _init_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / ".git").mkdir()
    monkeypatch.setenv("AME_REVIEW_PROJECT_ROOT", str(tmp_path))
    return tmp_path


def test_init_creates_expected_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _init_in(tmp_path, monkeypatch)
    assert init_cmd.cmd_init(_make_args()) == 0
    assert (root / ".ame-review" / "config.json").exists()
    assert (root / ".ame-review" / "review_prompt.txt").exists()
    assert (root / ".pre-commit-config.yaml").exists()
    assert (root / ".github" / "workflows" / "review_command.yml").exists()
    assert (root / ".github" / "workflows" / "review_reply.yml").exists()


def test_init_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _init_in(tmp_path, monkeypatch)
    assert init_cmd.cmd_init(_make_args()) == 0
    cfg = root / ".ame-review" / "config.json"
    cfg.write_text("CUSTOM", encoding="utf-8")
    assert init_cmd.cmd_init(_make_args()) == 0
    assert cfg.read_text(encoding="utf-8") == "CUSTOM"


def test_init_force_overwrites(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _init_in(tmp_path, monkeypatch)
    assert init_cmd.cmd_init(_make_args()) == 0
    cfg = root / ".ame-review" / "config.json"
    cfg.write_text("CUSTOM", encoding="utf-8")
    assert init_cmd.cmd_init(_make_args(force=True)) == 0
    assert cfg.read_text(encoding="utf-8") != "CUSTOM"


def test_init_ref_replacement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _init_in(tmp_path, monkeypatch)
    assert init_cmd.cmd_init(_make_args(ref="v1.2.3")) == 0
    wf = (root / ".github" / "workflows" / "review_command.yml").read_text(
        encoding="utf-8",
    )
    assert "@v1.2.3" in wf
    assert "system_ref: v1.2.3" in wf
    assert "__REF__" not in wf


def test_init_no_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _init_in(tmp_path, monkeypatch)
    assert init_cmd.cmd_init(_make_args(no_workflow=True)) == 0
    assert not (root / ".github").exists()


def test_init_requires_ref_unless_no_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_in(tmp_path, monkeypatch)
    assert init_cmd.cmd_init(_make_args(ref=None)) == 1


def _read_lines(rel: str) -> list[str]:
    # プロジェクトルート (tests/ の親) からの相対パスでワークフローを読む。
    root = Path(__file__).resolve().parent.parent
    return (root / rel).read_text(encoding="utf-8").splitlines()


def _comment_match_lines(lines: list[str]) -> list[str]:
    """ワークフローからコメント本文判定 (github.event.comment.body) の行を抽出する.

    ラッパと配布テンプレートでコマンド発火条件が常に一致することを機械的に検証し、
    片方だけ更新されるドリフトを検知する (Issue #68/#70/#71)。
    """
    return [ln.strip() for ln in lines if "github.event.comment.body" in ln]


def _command_lines(lines: list[str]) -> list[str]:
    return [ln.strip() for ln in lines if "command:" in ln and "comment.body" in ln]


def test_workflow_and_template_command_conditions_match() -> None:
    real = _read_lines(".github/workflows/review_command.yml")
    tmpl = _read_lines(
        "ame_ai_review_system/templates/workflow/review-command-wrapper.yml"
    )
    assert _comment_match_lines(real) == _comment_match_lines(tmpl)
    assert _command_lines(real) == _command_lines(tmpl)
