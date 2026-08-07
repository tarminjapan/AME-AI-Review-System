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
        "python": None,
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


def test_init_embeds_python_bin_in_preset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Issue #66: PEP 668 環境向けに Gate 1 フックの entry: へ実インタープリタを埋め込む。
    root = _init_in(tmp_path, monkeypatch)
    monkeypatch.setattr(init_cmd, "_verify_importable", lambda _p: True)
    custom = "/custom/venv/bin/python"
    assert init_cmd.cmd_init(_make_args(python=custom)) == 0
    cfg = (root / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert f"entry: {custom} -m ame_ai_review_system." in cfg
    assert "__PYTHON_BIN__" not in cfg


def test_init_python_bin_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _init_in(tmp_path, monkeypatch)
    monkeypatch.setenv("AME_INIT_PYTHON", "/env/python")
    monkeypatch.setattr(init_cmd, "_verify_importable", lambda _p: True)
    assert init_cmd.cmd_init(_make_args(python=None)) == 0
    cfg = (root / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "entry: /env/python -m ame_ai_review_system." in cfg


def test_init_falls_back_to_sys_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _init_in(tmp_path, monkeypatch)
    monkeypatch.delenv("AME_INIT_PYTHON", raising=False)
    monkeypatch.setattr(init_cmd, "_verify_importable", lambda _p: True)
    assert init_cmd.cmd_init(_make_args(python=None)) == 0
    cfg = (root / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    import sys

    assert f"entry: {sys.executable} -m ame_ai_review_system." in cfg


def test_init_explicit_python_unimportable_fails_fast(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Issue #66: 明示 --python で import 不可なら壊れた Gate 1 設定を書き出さず非ゼロ終了。
    root = _init_in(tmp_path, monkeypatch)
    monkeypatch.setattr(init_cmd, "_verify_importable", lambda _p: False)
    assert init_cmd.cmd_init(_make_args(python="/missing/python")) == 1
    assert not (root / ".pre-commit-config.yaml").exists()


def test_init_auto_python_unimportable_warns_but_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 自動解決 (env/sys.executable) で import 不可なら警告しつつ設定は書き出す。
    root = _init_in(tmp_path, monkeypatch)
    monkeypatch.setattr(init_cmd, "_verify_importable", lambda _p: False)
    assert init_cmd.cmd_init(_make_args(python=None, no_workflow=True)) == 0
    assert (root / ".pre-commit-config.yaml").exists()
