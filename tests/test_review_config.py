# pyright: basic
from __future__ import annotations

import io
import os
import tempfile
from collections.abc import Callable
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from ame_ai_review_system import paths, review_config
from ame_ai_review_system.review_config import (
    _referenced_subpaths,
    apply_repair_model,
    config_bool,
    excluded_package_reference_note,
    filter_review_diff,
    filter_review_targets,
    is_review_command,
    load_config,
    load_global_config,
    package_dir_rel,
    user_overrides,
)


def test_is_review_command_exact() -> None:
    assert is_review_command("/request-review")
    assert is_review_command("/review")


def test_is_review_command_with_args() -> None:
    assert is_review_command("/request-review @ame-ai-reviewer")
    assert is_review_command("/review please")


def test_is_review_command_multiline() -> None:
    assert is_review_command("  /request-review\n\nレビューお願いします")


def test_is_review_command_negative() -> None:
    assert not is_review_command("/requestreview")
    assert not is_review_command("request-review")
    assert not is_review_command("")
    assert not is_review_command("   ")
    assert not is_review_command("通常の返信コメントです")


def test_load_config_default_disabled() -> None:
    os.environ.pop("AME_REVIEW_CONFIG", None)
    cfg = load_config()
    assert "push_review_enabled" not in cfg
    assert cfg["engine"] == "claude"
    # Issue #55 I3: model 既定は None (claude は engine.py 側で sonnet にフォールバック)。
    assert cfg["model"] is None
    assert cfg["review_model"] is None
    # Issue #107: 既定 thinking は reasoning 予算枯渇を避けるため low。
    assert cfg["thinking"] == "low"
    assert cfg["review_budget_usd"] == pytest.approx(2.0)
    assert cfg["reply_budget_usd"] == pytest.approx(0.2)
    # Issue #40: エンジン情報バナーは既定で表示。
    assert cfg["show_engine_info_gate1"] is True
    assert cfg["show_engine_info_gate2"] is True
    # Issue #129: レビュー回数上限は Gate1 / Gate2 とも既定 3。
    assert cfg["precommit_max_reviews"] == 3
    assert cfg["pr_max_reviews"] == 3


def test_load_config_reads_file() -> None:
    old = os.environ.get("AME_REVIEW_CONFIG")
    old_user = os.environ.get("AME_REVIEW_USER_CONFIG")
    fd, name = tempfile.mkstemp(suffix=".json")
    nonexistent = Path(tempfile.gettempdir()) / "nonexistent_user_config.json"
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write('{"precommit_engine": "claude"}')
        os.environ["AME_REVIEW_CONFIG"] = name
        os.environ["AME_REVIEW_USER_CONFIG"] = str(nonexistent)
        cfg = load_config()
    finally:
        _restore_env("AME_REVIEW_CONFIG", old)
        _restore_env("AME_REVIEW_USER_CONFIG", old_user)
        Path(name).unlink(missing_ok=True)
    assert cfg["precommit_engine"] == "claude"


def test_cli_get_prints_default() -> None:
    nonexistent = Path(tempfile.gettempdir()) / "nonexistent_cli_config.json"
    old = os.environ.get("AME_REVIEW_CONFIG")
    try:
        os.environ["AME_REVIEW_CONFIG"] = str(nonexistent)
        output = _capture(
            lambda: review_config.main(
                ["review_config.py", "get", "engine"],
            ),
        )
    finally:
        _restore_env("AME_REVIEW_CONFIG", old)
    assert output.strip() == "claude"


def test_cli_is_review_command() -> None:
    output = _capture(
        lambda: review_config.main(
            ["review_config.py", "is-review-command", "/request-review"],
        ),
    )
    assert output.strip() == "true"


# ---------------------------
# Issue #129: レビュー回数上限アクセサ
# ---------------------------


def test_precommit_max_reviews_default() -> None:
    assert review_config.precommit_max_reviews() == 3


def test_precommit_max_reviews_custom() -> None:
    assert review_config.precommit_max_reviews({"precommit_max_reviews": 5}) == 5


def test_precommit_max_reviews_invalid_falls_back() -> None:
    # 0 / 負値 / 非 int は「上限なし = 無限レビュー」を許さないため既定 3 へ。
    assert review_config.precommit_max_reviews({"precommit_max_reviews": 0}) == 3
    assert review_config.precommit_max_reviews({"precommit_max_reviews": -1}) == 3
    assert review_config.precommit_max_reviews({"precommit_max_reviews": "abc"}) == 3
    assert review_config.precommit_max_reviews({}) == 3


def test_precommit_max_reviews_clamped_to_low_streak_plus_one() -> None:
    # Issue #134: LOW 連続 escape (固定 2) より先に blocking が通過しないよう、
    # 総ラウンド上限の最小値は LOW_STREAK_THRESHOLD + 1 (=3) にクランプする。
    assert (
        review_config.precommit_max_reviews({"precommit_max_reviews": 1})
        == review_config.LOW_STREAK_THRESHOLD + 1
    )
    assert (
        review_config.precommit_max_reviews({"precommit_max_reviews": 2})
        == review_config.LOW_STREAK_THRESHOLD + 1
    )
    # クランプ境界以上はそのまま反映される。
    assert review_config.precommit_max_reviews({"precommit_max_reviews": 3}) == 3
    assert review_config.precommit_max_reviews({"precommit_max_reviews": 4}) == 4


def test_low_streak_threshold_shared_across_gates() -> None:
    # Issue #134: Gate 1 と Gate 2 の LOW 連続閾値は単一の共有定数を参照し、
    # 片方だけ変更されて非対称化しないこと。
    from ame_ai_review_system import pr_streak, precommit_review

    assert precommit_review._LOW_STREAK_THRESHOLD == review_config.LOW_STREAK_THRESHOLD
    assert pr_streak._STREAK_THRESHOLD == review_config.LOW_STREAK_THRESHOLD


def test_pr_max_reviews_default() -> None:
    assert review_config.pr_max_reviews() == 3


def test_pr_max_reviews_custom() -> None:
    assert review_config.pr_max_reviews({"pr_max_reviews": 4}) == 4


def test_pr_max_reviews_invalid_falls_back() -> None:
    assert review_config.pr_max_reviews({"pr_max_reviews": 0}) == 3
    assert review_config.pr_max_reviews({"pr_max_reviews": -5}) == 3
    assert review_config.pr_max_reviews({"pr_max_reviews": "x"}) == 3
    assert review_config.pr_max_reviews({}) == 3


def test_user_config_overrides_default_config() -> None:
    old_conf = os.environ.get("AME_REVIEW_CONFIG")
    old_user = os.environ.get("AME_REVIEW_USER_CONFIG")
    fd_conf, name_conf = tempfile.mkstemp(suffix=".json")
    fd_user, name_user = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd_conf, "w", encoding="utf-8") as fh:
            fh.write('{"engine": "opencode", "thinking": "medium"}')
        with os.fdopen(fd_user, "w", encoding="utf-8") as fh:
            fh.write('{"thinking": "high", "review_budget_usd": 3.0}')
        os.environ["AME_REVIEW_CONFIG"] = name_conf
        os.environ["AME_REVIEW_USER_CONFIG"] = name_user
        cfg = load_config()
    finally:
        _restore_env("AME_REVIEW_CONFIG", old_conf)
        _restore_env("AME_REVIEW_USER_CONFIG", old_user)
        Path(name_conf).unlink(missing_ok=True)
        Path(name_user).unlink(missing_ok=True)
    assert cfg["engine"] == "opencode"
    assert cfg["thinking"] == "high"
    assert cfg["review_budget_usd"] == pytest.approx(3.0)


def test_load_global_config_missing_returns_empty() -> None:
    old_global = os.environ.get("AME_REVIEW_GLOBAL_CONFIG")
    nonexistent = Path(tempfile.gettempdir()) / "nonexistent_global_config.json"
    try:
        os.environ["AME_REVIEW_GLOBAL_CONFIG"] = str(nonexistent)
        assert load_global_config() == {}
    finally:
        _restore_env("AME_REVIEW_GLOBAL_CONFIG", old_global)


def test_load_global_config_warns_on_malformed_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Issue #120: グローバル設定の JSON が壊れている場合は警告しつつ空 dict を返す。
    old_global = os.environ.get("AME_REVIEW_GLOBAL_CONFIG")
    fd, name = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("{broken json")
        os.environ["AME_REVIEW_GLOBAL_CONFIG"] = name
        assert load_global_config() == {}
    finally:
        _restore_env("AME_REVIEW_GLOBAL_CONFIG", old_global)
        Path(name).unlink(missing_ok=True)
    assert "JSON が壊れている" in capsys.readouterr().err


def test_load_global_config_warns_on_non_object(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Issue #120: グローバル設定が配列等の非オブジェクトも警告して無視する。
    old_global = os.environ.get("AME_REVIEW_GLOBAL_CONFIG")
    fd, name = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("[1, 2, 3]")
        os.environ["AME_REVIEW_GLOBAL_CONFIG"] = name
        assert load_global_config() == {}
    finally:
        _restore_env("AME_REVIEW_GLOBAL_CONFIG", old_global)
        Path(name).unlink(missing_ok=True)
    assert "JSON オブジェクトでない" in capsys.readouterr().err


def test_load_config_applies_global_when_no_repo() -> None:
    # Issue #120: リポジトリ設定が無ければグローバル設定が適用される。
    old_global = os.environ.get("AME_REVIEW_GLOBAL_CONFIG")
    old_conf = os.environ.get("AME_REVIEW_CONFIG")
    old_user = os.environ.get("AME_REVIEW_USER_CONFIG")
    fd, name_global = tempfile.mkstemp(suffix=".json")
    nonexistent = Path(tempfile.gettempdir()) / "nonexistent_repo_config.json"
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(
                '{"precommit_engine": "claude", "precommit_model": "sonnet",'
                ' "precommit_thinking": "medium"}',
            )
        os.environ["AME_REVIEW_GLOBAL_CONFIG"] = name_global
        os.environ["AME_REVIEW_CONFIG"] = str(nonexistent)
        os.environ["AME_REVIEW_USER_CONFIG"] = str(nonexistent)
        cfg = load_config()
    finally:
        _restore_env("AME_REVIEW_GLOBAL_CONFIG", old_global)
        _restore_env("AME_REVIEW_CONFIG", old_conf)
        _restore_env("AME_REVIEW_USER_CONFIG", old_user)
        Path(name_global).unlink(missing_ok=True)
    assert cfg["precommit_engine"] == "claude"
    assert cfg["precommit_model"] == "sonnet"
    assert cfg["precommit_thinking"] == "medium"


def test_load_config_repo_overrides_global() -> None:
    # Issue #120: 優先順位は リポジトリ設定 > グローバル設定。
    old_global = os.environ.get("AME_REVIEW_GLOBAL_CONFIG")
    old_conf = os.environ.get("AME_REVIEW_CONFIG")
    old_user = os.environ.get("AME_REVIEW_USER_CONFIG")
    fd_global, name_global = tempfile.mkstemp(suffix=".json")
    fd_conf, name_conf = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd_global, "w", encoding="utf-8") as fh:
            fh.write('{"precommit_engine": "claude", "precommit_thinking": "low"}')
        with os.fdopen(fd_conf, "w", encoding="utf-8") as fh:
            fh.write('{"precommit_engine": "opencode"}')
        os.environ["AME_REVIEW_GLOBAL_CONFIG"] = name_global
        os.environ["AME_REVIEW_CONFIG"] = name_conf
        os.environ["AME_REVIEW_USER_CONFIG"] = str(
            Path(tempfile.gettempdir()) / "nonexistent_user_config.json"
        )
        cfg = load_config()
    finally:
        _restore_env("AME_REVIEW_GLOBAL_CONFIG", old_global)
        _restore_env("AME_REVIEW_CONFIG", old_conf)
        _restore_env("AME_REVIEW_USER_CONFIG", old_user)
        Path(name_global).unlink(missing_ok=True)
        Path(name_conf).unlink(missing_ok=True)
    assert cfg["precommit_engine"] == "opencode"
    # thinking はグローバル値が残る (リポジトリは engine のみ上書き)。
    assert cfg["precommit_thinking"] == "low"


def test_load_config_global_ignores_non_precommit_keys() -> None:
    # Issue #120: グローバル設定は Gate 1 (precommit_*) に限定され、
    # model 等の Gate 2 キーは波及しない。
    old_global = os.environ.get("AME_REVIEW_GLOBAL_CONFIG")
    old_conf = os.environ.get("AME_REVIEW_CONFIG")
    old_user = os.environ.get("AME_REVIEW_USER_CONFIG")
    fd, name_global = tempfile.mkstemp(suffix=".json")
    nonexistent = Path(tempfile.gettempdir()) / "nonexistent_repo_config.json"
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(
                '{"precommit_engine": "claude", "model": "sonnet",'
                ' "review_budget_usd": 9.9}',
            )
        os.environ["AME_REVIEW_GLOBAL_CONFIG"] = name_global
        os.environ["AME_REVIEW_CONFIG"] = str(nonexistent)
        os.environ["AME_REVIEW_USER_CONFIG"] = str(nonexistent)
        cfg = load_config()
    finally:
        _restore_env("AME_REVIEW_GLOBAL_CONFIG", old_global)
        _restore_env("AME_REVIEW_CONFIG", old_conf)
        _restore_env("AME_REVIEW_USER_CONFIG", old_user)
        Path(name_global).unlink(missing_ok=True)
    assert cfg["precommit_engine"] == "claude"
    assert cfg["model"] is None  # グローバルの model は取り込まれない
    assert cfg["review_budget_usd"] == pytest.approx(2.0)  # 既定値のまま


def test_user_overrides_includes_user_config() -> None:
    old_conf = os.environ.get("AME_REVIEW_CONFIG")
    old_user = os.environ.get("AME_REVIEW_USER_CONFIG")
    fd_conf, name_conf = tempfile.mkstemp(suffix=".json")
    fd_user, name_user = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd_conf, "w", encoding="utf-8") as fh:
            fh.write('{"engine": "opencode"}')
        with os.fdopen(fd_user, "w", encoding="utf-8") as fh:
            fh.write('{"thinking": "low"}')
        os.environ["AME_REVIEW_CONFIG"] = name_conf
        os.environ["AME_REVIEW_USER_CONFIG"] = name_user
        overrides = user_overrides()
    finally:
        _restore_env("AME_REVIEW_CONFIG", old_conf)
        _restore_env("AME_REVIEW_USER_CONFIG", old_user)
        Path(name_conf).unlink(missing_ok=True)
        Path(name_user).unlink(missing_ok=True)
    assert overrides["engine"] == "opencode"
    assert overrides["thinking"] == "low"


def test_missing_user_config_does_not_break() -> None:
    old = os.environ.get("AME_REVIEW_CONFIG")
    old_user = os.environ.get("AME_REVIEW_USER_CONFIG")
    fd, name = tempfile.mkstemp(suffix=".json")
    nonexistent = Path(tempfile.gettempdir()) / "nonexistent_user_config.json"
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write('{"engine": "claude"}')
        os.environ["AME_REVIEW_CONFIG"] = name
        os.environ.pop("AME_REVIEW_USER_CONFIG", None)
        # Point to a non-existent user config
        os.environ["AME_REVIEW_USER_CONFIG"] = str(nonexistent)
        cfg = load_config()
    finally:
        _restore_env("AME_REVIEW_CONFIG", old)
        _restore_env("AME_REVIEW_USER_CONFIG", old_user)
        Path(name).unlink(missing_ok=True)
    assert cfg["engine"] == "claude"


def test_config_bool_handles_json_bool() -> None:
    assert config_bool({"show_engine_info_gate2": True}, "show_engine_info_gate2")
    assert not config_bool({"show_engine_info_gate2": False}, "show_engine_info_gate2")


def test_config_bool_handles_string_false() -> None:
    # 手編集で "false" が文字列として書かれても false と解釈する (Issue #40)。
    assert not config_bool(
        {"show_engine_info_gate2": "false"},
        "show_engine_info_gate2",
    )
    assert config_bool(
        {"show_engine_info_gate2": "true"},
        "show_engine_info_gate2",
    )


def test_config_bool_default_when_missing() -> None:
    assert config_bool({}, "show_engine_info_gate2")
    assert not config_bool({}, "show_engine_info_gate2", default=False)


# ============================================================================
# Issue #37: vendored ame_ai_review_system 配下のレビュー除外
# ============================================================================


def _exclude_package(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    pkg = root / "ame_ai_review_system"
    pkg.mkdir(parents=True)
    monkeypatch.setattr(paths, "package_dir", lambda: pkg)
    monkeypatch.setattr(paths, "project_root", lambda: root)
    monkeypatch.setattr(
        review_config,
        "load_config",
        lambda: {"review_include_package_dir": False},
    )


def test_package_dir_rel_returns_top_level_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exclude_package(monkeypatch, tmp_path)
    assert package_dir_rel() == "ame_ai_review_system"


def test_package_dir_rel_returns_nested_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    pkg = root / "vendor" / "ame_ai_review_system"
    pkg.mkdir(parents=True)
    monkeypatch.setattr(paths, "package_dir", lambda: pkg)
    monkeypatch.setattr(paths, "project_root", lambda: root)
    monkeypatch.setattr(
        review_config,
        "load_config",
        lambda: {"review_include_package_dir": False},
    )
    assert package_dir_rel() == "vendor/ame_ai_review_system"
    files = [
        "vendor/ame_ai_review_system/main.py",
        "vendor/other.py",
        "src/app.py",
    ]
    assert filter_review_targets(files) == ["vendor/other.py", "src/app.py"]


def test_package_dir_rel_none_when_not_vendored(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    pkg = tmp_path / "site-packages" / "ame_ai_review_system"
    pkg.mkdir(parents=True)
    monkeypatch.setattr(paths, "package_dir", lambda: pkg)
    monkeypatch.setattr(paths, "project_root", lambda: root)
    assert package_dir_rel() is None


def test_apply_repair_model_overrides_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_config,
        "load_config",
        lambda: {"review_repair_model": "opencode-go/gpt-5.6-luna"},
    )
    settings = {"model": "opencode-go/deepseek-v4-flash"}
    assert apply_repair_model(settings) == {
        "model": "opencode-go/gpt-5.6-luna",
    }


def test_apply_repair_model_passthrough_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_config,
        "load_config",
        lambda: {"review_repair_model": None},
    )
    settings = {"model": "opencode-go/deepseek-v4-flash"}
    assert apply_repair_model(settings) == settings


def test_filter_review_targets_keeps_all_when_include_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_config,
        "load_config",
        lambda: {"review_include_package_dir": True},
    )
    files = ["ame_ai_review_system/main.py", "src/app.py"]
    assert filter_review_targets(files) == files


def test_filter_review_targets_excludes_package_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exclude_package(monkeypatch, tmp_path)
    files = [
        "ame_ai_review_system/main.py",
        "ame_ai_review_system/sub/foo.py",
        "src/app.py",
        "tests/test_main.py",
    ]
    assert filter_review_targets(files) == ["src/app.py", "tests/test_main.py"]


_DIFF = (
    "diff --git a/ame_ai_review_system/main.py b/ame_ai_review_system/main.py\n"
    "index 1234567..abcdefg 100644\n"
    "--- a/ame_ai_review_system/main.py\n"
    "+++ b/ame_ai_review_system/main.py\n"
    "@@ -1,1 +1,1 @@\n"
    "-x\n"
    "+y\n"
    "diff --git a/src/app.py b/src/app.py\n"
    "index 1234567..abcdefg 100644\n"
    "--- a/src/app.py\n"
    "+++ b/src/app.py\n"
    "@@ -1,1 +1,1 @@\n"
    "-x\n"
    "+y\n"
)


def test_filter_review_diff_keeps_all_when_include_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_config,
        "load_config",
        lambda: {"review_include_package_dir": True},
    )
    assert filter_review_diff(_DIFF) == _DIFF


def test_filter_review_diff_excludes_package_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exclude_package(monkeypatch, tmp_path)
    result = filter_review_diff(_DIFF)
    assert "ame_ai_review_system/main.py" not in result
    assert "src/app.py" in result
    assert "-x" in result
    assert "+y" in result


def test_filter_review_diff_excludes_rename_under_package_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exclude_package(monkeypatch, tmp_path)
    rename_diff = (
        "diff --git a/ame_ai_review_system/old.py b/ame_ai_review_system/new.py\n"
        "similarity index 90%\n"
        "rename from ame_ai_review_system/old.py\n"
        "rename to ame_ai_review_system/new.py\n"
        "--- a/ame_ai_review_system/old.py\n"
        "+++ b/ame_ai_review_system/new.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-x\n"
        "+y\n"
    )
    assert not filter_review_diff(rename_diff)


def test_filter_review_diff_excludes_binary_diff_under_package_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exclude_package(monkeypatch, tmp_path)
    binary_diff = (
        "diff --git a/ame_ai_review_system/data.bin b/ame_ai_review_system/data.bin\n"
        "index 1234567..abcdefg 100644\n"
        "Binary files a/ame_ai_review_system/data.bin and b/ame_ai_review_system/data.bin differ\n"
    )
    assert not filter_review_diff(binary_diff)


def test_filter_review_diff_excludes_mode_change_under_package_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exclude_package(monkeypatch, tmp_path)
    mode_diff = (
        "diff --git a/ame_ai_review_system/run.sh b/ame_ai_review_system/run.sh\n"
        "old mode 100644\n"
        "new mode 100755\n"
    )
    assert not filter_review_diff(mode_diff)


def test_filter_review_diff_excludes_quoted_binary_path_under_package_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exclude_package(monkeypatch, tmp_path)
    quoted_diff = (
        'diff --git "a/ame_ai_review_system/my file.bin" '
        '"b/ame_ai_review_system/my file.bin"\n'
        "index 1234567..abcdefg 100644\n"
        'Binary files "a/ame_ai_review_system/my file.bin" and '
        '"b/ame_ai_review_system/my file.bin" differ\n'
    )
    assert not filter_review_diff(quoted_diff)


def test_filter_review_diff_keeps_quoted_path_outside_package_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exclude_package(monkeypatch, tmp_path)
    quoted_diff = (
        'diff --git "a/src/my file.txt" "b/src/my file.txt"\n'
        "index 1234567..abcdefg 100644\n"
        'Binary files "a/src/my file.txt" and "b/src/my file.txt" differ\n'
    )
    result = filter_review_diff(quoted_diff)
    assert 'diff --git "a/src/my file.txt"' in result
    assert "Binary files" in result


def test_filter_review_diff_keeps_cross_boundary_rename(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exclude_package(monkeypatch, tmp_path)
    rename_diff = (
        "diff --git a/src/old.py b/ame_ai_review_system/new.py\n"
        "similarity index 80%\n"
        "rename from src/old.py\n"
        "rename to ame_ai_review_system/new.py\n"
        "--- a/src/old.py\n"
        "+++ b/ame_ai_review_system/new.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-x\n"
        "+y\n"
    )
    result = filter_review_diff(rename_diff)
    assert "src/old.py" in result


def test_filter_review_diff_excludes_add_under_package_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exclude_package(monkeypatch, tmp_path)
    add_diff = (
        "diff --git a/ame_ai_review_system/new.py b/ame_ai_review_system/new.py\n"
        "new file mode 100644\n"
        "index 0000000..1234567\n"
        "--- /dev/null\n"
        "+++ b/ame_ai_review_system/new.py\n"
        "@@ -0,0 +1 @@\n"
        "+print('hi')\n"
    )
    assert not filter_review_diff(add_diff)


def test_filter_review_diff_excludes_delete_under_package_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exclude_package(monkeypatch, tmp_path)
    delete_diff = (
        "diff --git a/ame_ai_review_system/old.py b/ame_ai_review_system/old.py\n"
        "deleted file mode 100644\n"
        "index 1234567..0000000\n"
        "--- a/ame_ai_review_system/old.py\n"
        "+++ /dev/null\n"
        "@@ -1 +0,0 @@\n"
        "-x\n"
    )
    assert not filter_review_diff(delete_diff)


def test_filter_review_diff_empty_input() -> None:
    assert not filter_review_diff("")


def test_filter_review_diff_after_compact_diff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from ame_ai_review_system.diff_utils import compact_diff

    _exclude_package(monkeypatch, tmp_path)
    diff = (
        "diff --git a/ame_ai_review_system/main.py b/ame_ai_review_system/main.py\n"
        "index 1234567..abcdefg 100644\n"
        "--- a/ame_ai_review_system/main.py\n"
        "+++ b/ame_ai_review_system/main.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-x\n"
        "+y\n"
        "diff --git a/src/app.py b/src/app.py\n"
        "index 1234567..abcdefg 100644\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-x\n"
        "+y\n"
    )
    result = filter_review_diff(compact_diff(diff))
    assert "ame_ai_review_system/main.py" not in result
    assert "src/app.py" in result


# ============================================================================
# Issue #47: 除外した vendored パッケージの参照注記
# ============================================================================


def _package_exists(monkeypatch: pytest.MonkeyPatch, *, exists: bool) -> None:
    def _exists(_rel: str) -> bool:
        return exists

    def _subpaths_exist(_rel: str, _subpaths: set[str]) -> bool:
        return exists

    monkeypatch.setattr(review_config, "_package_exists_in_repo", _exists)
    monkeypatch.setattr(review_config, "_package_subpaths_exist", _subpaths_exist)


def test_reference_note_returned_when_diff_references_package(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exclude_package(monkeypatch, tmp_path)
    _package_exists(monkeypatch, exists=True)
    diff = (
        "diff --git a/.pre-commit-config.yaml b/.pre-commit-config.yaml\n"
        "+- id: ai-skip-guard\n"
        "+  entry: python3 -m ame_ai_review_system.skip_guard\n"
    )
    note = excluded_package_reference_note([], diff)
    assert "ame_ai_review_system" in note
    assert "レビュー対象外" in note
    assert "存在" in note


def test_reference_note_returned_when_files_reference_package(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exclude_package(monkeypatch, tmp_path)
    _package_exists(monkeypatch, exists=True)
    note = excluded_package_reference_note(
        ["README.md"],
        "diff --git a/README.md b/README.md\n+ame_ai_review_system/engines/ts の導入",
    )
    assert "ame_ai_review_system" in note


def test_reference_note_empty_when_include_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    pkg = root / "ame_ai_review_system"
    pkg.mkdir(parents=True)
    monkeypatch.setattr(paths, "package_dir", lambda: pkg)
    monkeypatch.setattr(paths, "project_root", lambda: root)
    monkeypatch.setattr(
        review_config,
        "load_config",
        lambda: {"review_include_package_dir": True},
    )
    assert not excluded_package_reference_note(
        [],
        "python3 -m ame_ai_review_system.skip_guard",
    )


def test_reference_note_empty_when_no_reference(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exclude_package(monkeypatch, tmp_path)
    _package_exists(monkeypatch, exists=True)
    assert not excluded_package_reference_note(["src/app.py"], "+diff content")


def test_reference_note_empty_when_package_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exclude_package(monkeypatch, tmp_path)
    _package_exists(monkeypatch, exists=False)
    assert not excluded_package_reference_note(
        [],
        "python3 -m ame_ai_review_system.skip_guard",
    )


def test_reference_note_empty_when_not_vendored(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    pkg = tmp_path / "site-packages" / "ame_ai_review_system"
    pkg.mkdir(parents=True)
    monkeypatch.setattr(paths, "package_dir", lambda: pkg)
    monkeypatch.setattr(paths, "project_root", lambda: root)
    monkeypatch.setattr(
        review_config,
        "load_config",
        lambda: {"review_include_package_dir": False},
    )
    assert not excluded_package_reference_note(
        [],
        "python3 -m ame_ai_review_system.skip_guard",
    )


def test_reference_note_ignores_similar_but_different_names(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _exclude_package(monkeypatch, tmp_path)
    _package_exists(monkeypatch, exists=True)
    # 語境界 (\b) により `xame_ai_review_system` や `ame_ai_review_system2` は誤検知しない。
    assert not excluded_package_reference_note(
        [],
        "+xame_ai_review_system and ame_ai_review_system2",
    )


def test_referenced_subpaths_extracts_module() -> None:
    assert _referenced_subpaths(
        "ame_ai_review_system",
        "python3 -m ame_ai_review_system.skip_guard --exit-code",
    ) == {"skip_guard"}


def test_referenced_subpaths_extracts_path() -> None:
    assert _referenced_subpaths(
        "ame_ai_review_system",
        "npm --prefix ame_ai_review_system/engines/ts install",
    ) == {"engines/ts"}


def test_referenced_subpaths_empty_without_suffix() -> None:
    assert not _referenced_subpaths(
        "ame_ai_review_system",
        "the ame_ai_review_system package is vendored",
    )


def test_referenced_subpaths_strips_trailing_punctuation() -> None:
    assert _referenced_subpaths(
        "ame_ai_review_system",
        "ame_ai_review_system.skip_guard.",
    ) == {"skip_guard"}


def test_reference_note_empty_when_referenced_subpath_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # 参照されたサブモジュールが実在しない場合 (typo 等) は注記を付けない。
    _exclude_package(monkeypatch, tmp_path)
    _package_exists(monkeypatch, exists=False)
    # _package_exists_in_repo は True だが、サブパス検証だけ失敗するケースを再現する。
    monkeypatch.setattr(
        review_config,
        "_package_exists_in_repo",
        lambda _rel: True,
    )
    assert not excluded_package_reference_note(
        [],
        "python3 -m ame_ai_review_system.skip_guard",
    )


def test_reference_note_verifies_subpath_via_git(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # 実 git リポジトリで、参照されたサブモジュールが実在する場合のみ注記が付くことを確認する。
    import subprocess as sp

    root = tmp_path / "repo"
    pkg = root / "ame_ai_review_system"
    pkg.mkdir(parents=True)
    (pkg / "skip_guard.py").write_text("def main():\n    pass\n", encoding="utf-8")
    sp.run(["git", "init", "-q"], cwd=root, check=True)
    sp.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    sp.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    sp.run(["git", "add", "."], cwd=root, check=True)
    sp.run(["git", "commit", "-qm", "init"], cwd=root, check=True)
    monkeypatch.setattr(paths, "package_dir", lambda: pkg)
    monkeypatch.setattr(paths, "project_root", lambda: root)
    monkeypatch.setattr(
        review_config,
        "load_config",
        lambda: {"review_include_package_dir": False},
    )
    diff = "+  entry: python3 -m ame_ai_review_system.skip_guard"
    assert "vendored" in excluded_package_reference_note([], diff)
    # 参照先が存在しないサブモジュールの場合、注記は付かない。
    missing_diff = "+  entry: python3 -m ame_ai_review_system.no_such_module"
    assert not excluded_package_reference_note([], missing_diff)
    # ドット連鎖の末尾が属性アクセス (main.run()) でも、モジュール本体が存在すれば注記が付く。
    (pkg / "main.py").write_text("def run():\n    pass\n", encoding="utf-8")
    sp.run(["git", "add", "."], cwd=root, check=True)
    sp.run(["git", "commit", "-qm", "add main"], cwd=root, check=True)
    attr_diff = "+x = ame_ai_review_system.main.run()"
    assert "vendored" in excluded_package_reference_note([], attr_diff)


def _restore_env(key: str, old: str | None) -> None:
    if old is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = old


def _capture(fn: Callable[[], int]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn()
    return buf.getvalue()
