# pyright: basic
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from ame_ai_review_system import (
    paths,
    post_commit_reset,
    precommit_review,
    precommit_state,
    review_config,
)
from ame_ai_review_system.precommit_review import (
    _build_prompt as build_prompt,
)
from ame_ai_review_system.precommit_review import (
    _decide as decide,
)
from ame_ai_review_system.precommit_review import (
    _format_issue as format_issue,
)
from ame_ai_review_system.precommit_review import (
    _is_blocking as is_blocking,
)
from ame_ai_review_system.precommit_review import (
    _run_static_checks as run_static_checks,
)
from ame_ai_review_system.precommit_review import (
    _truncate_diff as truncate_diff,
)
from ame_ai_review_system.stale_detect import comment_text as stale_comment_text

# ---------------------------
# decide / is_blocking / truncate_diff (pure functions)
# ---------------------------


def test_decide_zero_issues_passes_and_resets() -> None:
    allow, new_streak, reason = decide([], 2)
    assert allow is True
    assert new_streak == 0
    assert "0 件" in reason


def test_decide_blocking_resets_streak() -> None:
    comments = [{"severity": "HIGH"}]
    allow, new_streak, reason = decide(comments, 2)
    assert allow is False
    assert new_streak == 0
    assert "blocking" in reason


def test_decide_low_only_streak_0_fails() -> None:
    comments = [{"severity": "LOW"}]
    allow, new_streak, _ = decide(comments, 0)
    assert allow is False
    assert new_streak == 1


def test_decide_low_only_streak_1_passes() -> None:
    comments = [{"severity": "LOW"}]
    allow, new_streak, reason = decide(comments, 1)
    assert allow is True
    assert new_streak == 2
    assert "無限ループ回避" in reason


def test_decide_low_only_streak_2_passes() -> None:
    comments = [{"severity": "LOW"}]
    allow, new_streak, reason = decide(comments, 2)
    assert allow is True
    assert new_streak == 3
    assert "無限ループ回避" in reason


def test_decide_mixed_severity_blocks_and_resets() -> None:
    comments = [{"severity": "LOW"}, {"severity": "CRITICAL"}]
    allow, new_streak, _ = decide(comments, 1)
    assert allow is False
    assert new_streak == 0


def test_decide_multiple_blocking() -> None:
    comments = [{"severity": "HIGH"}, {"severity": "MIDDLE"}]
    allow, new_streak, reason = decide(comments, 0)
    assert allow is False
    assert new_streak == 0
    assert "2 件" in reason


def test_is_blocking_case_insensitive() -> None:
    # fail-closed: LOW/INFO 以外は unknown も含めて blocking 扱い。
    assert is_blocking({"severity": "critical"})
    assert is_blocking({"severity": "High"})
    assert is_blocking({"severity": "MIDDLE"})
    assert is_blocking({"severity": "WARNING"})
    assert is_blocking({"severity": "weird-unknown"})
    assert is_blocking({"severity": ""})
    assert is_blocking({})
    assert not is_blocking({"severity": "LOW"})
    assert not is_blocking({"severity": "INFO"})
    assert not is_blocking({"severity": "low"})


def test_is_blocking_whitespace_tolerant() -> None:
    assert is_blocking({"severity": "  HIGH  "})


# ---------------------------
# _demote_stale_comments (Issue #55 B2)
# ---------------------------


def _issue(severity: str, title: str) -> dict[str, Any]:
    return {"severity": severity, "title": title, "body": f"{title} の詳細"}


def test_demote_stale_no_history_unchanged() -> None:
    comments = [_issue("HIGH", "バグが残っています")]
    out, stale = precommit_review._demote_stale_comments(comments, [])
    assert stale is False
    assert out == comments


def test_demote_stale_identical_issue_demotes_blocking() -> None:
    # 前回レビューと同一のコメントが繰り返されたらそのコメントだけ LOW へ降格する。
    # severity は比較対象から除外されるため HIGH/MIDDLE の揺れでも検出できる。
    prev = stale_comment_text(_issue("HIGH", "バグが残っています"))
    current = [_issue("MIDDLE", "バグが残っています")]
    out, stale = precommit_review._demote_stale_comments(current, [prev])
    assert stale is True
    assert all(c["severity"] == "LOW" for c in out)


def test_demote_stale_different_issue_keeps_severity() -> None:
    prev = stale_comment_text(_issue("HIGH", "セキュリティホール"))
    current = [_issue("HIGH", "別のバグ")]
    out, stale = precommit_review._demote_stale_comments(current, [prev])
    assert stale is False
    assert out[0]["severity"] == "HIGH"


def test_demote_stale_mixed_keeps_new_blocking() -> None:
    # 繰り返し指摘の中に新規の HIGH が混ざっても、新規分は降格しない (コメント単位)。
    prev = stale_comment_text(_issue("MIDDLE", "バグが残っています"))
    current = [
        _issue("MIDDLE", "バグが残っています"),
        _issue("HIGH", "新規のセキュリティ問題"),
    ]
    out, stale = precommit_review._demote_stale_comments(current, [prev])
    assert stale is True
    assert out[0]["severity"] == "LOW"
    assert out[1]["severity"] == "HIGH"


def test_demote_stale_empty_current_unchanged() -> None:
    out, stale = precommit_review._demote_stale_comments([], ["prev text"])
    assert stale is False
    assert out == []


def test_demote_stale_same_target_repost_demoted() -> None:
    # Issue #67: 修正済みの指摘が本文を言い換えて再投稿されても、path + line + title が
    # 同じなら stale と判定して LOW へ降格する。
    same_target = {
        "severity": "MIDDLE",
        "path": "src/app.py",
        "line": 42,
        "title": "バグが残っています",
        "body": "元の指摘詳細文",
    }
    prev = [stale_comment_text(same_target)]
    reposted = [
        {
            "severity": "MIDDLE",
            "path": "src/app.py",
            "line": 42,
            "title": "バグが残っています",
            "body": "言い換えた全く別の詳細文です",
        },
    ]
    out, stale = precommit_review._demote_stale_comments(reposted, prev)
    assert stale is True
    assert out[0]["severity"] == "LOW"


def test_demote_stale_different_path_keeps_severity() -> None:
    # path が異なれば別の指摘として降格しない。
    prev = [
        stale_comment_text(
            {"path": "src/a.py", "line": 1, "title": "バグ", "body": "x"},
        ),
    ]
    current = [
        {
            "severity": "HIGH",
            "path": "src/b.py",
            "line": 1,
            "title": "バグ",
            "body": "x",
        },
    ]
    out, stale = precommit_review._demote_stale_comments(current, prev)
    assert stale is False
    assert out[0]["severity"] == "HIGH"


# ---------------------------
# _is_test_file / _test_target_candidates (Issue #55 B1)
# ---------------------------


def test_is_test_file_variants() -> None:
    assert precommit_review._is_test_file("tests/test_main.py")
    assert precommit_review._is_test_file("tests/foo/test_bar.py")
    assert precommit_review._is_test_file("test_foo.py")
    assert precommit_review._is_test_file("foo_test.py")
    assert not precommit_review._is_test_file("src/app.py")
    assert not precommit_review._is_test_file("tests/fixtures/data.json")


def test_test_target_candidates_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 候補生成はパッケージディレクトリに依存するため、テストでは None に固定する。
    monkeypatch.setattr(review_config, "package_dir_rel", lambda: None)
    assert precommit_review._test_target_candidates("tests/test_main.py") == [
        "main.py",
        "src/main.py",
    ]
    assert precommit_review._test_target_candidates("tests/foo/test_bar.py") == [
        "foo/bar.py",
        "src/foo/bar.py",
    ]
    assert precommit_review._test_target_candidates("src/app.py") == []


def test_test_target_candidates_includes_vendored_package_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # vendored パッケージ配下に実体がある場合は <pkg>/<rel> も候補に加える。
    monkeypatch.setattr(
        review_config,
        "package_dir_rel",
        lambda: "ame_ai_review_system",
    )
    assert precommit_review._test_target_candidates("tests/test_engine.py") == [
        "engine.py",
        "src/engine.py",
        "ame_ai_review_system/engine.py",
    ]


def test_truncate_diff_short_unchanged() -> None:
    diff = "line1\nline2\n"
    assert truncate_diff(diff) == diff


def test_truncate_diff_empty_unchanged() -> None:
    assert not truncate_diff("")


def test_truncate_diff_long_gets_shorter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Issue #62: wrapper は priority 戦略 (markers 未検出時は head+tail) を使う。
    # 環境設定 (max_diff_lines) に依存しないよう load_config を既定へ固定する。
    monkeypatch.setattr(review_config, "load_config", dict)
    diff = "\n".join(f"line{i}" for i in range(5000))
    truncated = truncate_diff(diff)
    assert "truncated" in truncated
    assert truncated.count("\n") < diff.count("\n")


def test_truncate_diff_closes_unmatched_code_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 開いた ``` が切詰めで閉じられない場合、閉じタグを補完すること。
    monkeypatch.setattr(review_config, "load_config", dict)
    diff = "```diff\n" + "\n".join(f"line{i}" for i in range(5000))
    truncated = truncate_diff(diff)
    assert truncated.count("```") % 2 == 0


def test_truncate_diff_keeps_staged_section_when_branch_overflows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Issue #62: ステージ済み差分 (優先セクション) は全行保持され、ブランチ差分の
    # 末尾 (後方ファイル) も可視になること。ブランチ冒頭は切り捨てられる。
    monkeypatch.setattr(review_config, "load_config", dict)
    staged = "### ステージ済み差分\n\n```diff\nSTAGED_LINE\n```"
    branch_lines = "\n".join(f"branch{i}" for i in range(5000))
    branch = f"### ブランチ差分\n\n```diff\n{branch_lines}\n```"
    diff = f"{staged}\n\n{branch}"
    truncated = truncate_diff(diff)
    assert "STAGED_LINE" in truncated
    assert "branch4999" in truncated
    assert "branch0" not in truncated
    assert "truncated" in truncated


def test_truncate_diff_at_boundary_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_config, "load_config", dict)
    diff = "\n".join(f"line{i}" for i in range(4000))
    assert truncate_diff(diff) == diff


# ---------------------------
# format_issue / build_prompt
# ---------------------------


def test_format_issue_renders_fields() -> None:
    out = format_issue(
        {
            "severity": "high",
            "path": "src/app.py",
            "line": 42,
            "title": "bug",
            "body": "fix me",
        },
    )
    assert "[HIGH]" in out
    assert "src/app.py:42" in out
    assert "bug" in out
    assert "fix me" in out


def test_format_issue_missing_fields_safe() -> None:
    out = format_issue({})
    assert "[?]" in out
    assert "?:?" in out


def test_build_prompt_contains_required_sections() -> None:
    prompt = build_prompt(
        "main",
        "feature/x",
        ["src/a.py", "src/b.py"],
        "diff content",
        "BASE PROMPT",
    )
    assert prompt.startswith("BASE PROMPT")
    assert "feature/x" in prompt
    assert "src/a.py" in prompt
    assert "src/b.py" in prompt
    assert "diff content" in prompt


def test_build_prompt_adds_reference_note_for_excluded_package(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Issue #47: 除外した vendored パッケージが差分から参照されるとプロンプトへ注記される。
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
    monkeypatch.setattr(review_config, "_package_exists_in_repo", lambda _rel: True)
    monkeypatch.setattr(
        review_config,
        "_package_subpaths_exist",
        lambda _rel, _subpaths: True,
    )
    prompt = build_prompt(
        "main",
        "feature/x",
        [".pre-commit-config.yaml"],
        "python3 -m ame_ai_review_system.skip_guard を追加",
        "BASE PROMPT",
    )
    assert "注記: vendored パッケージの参照" in prompt
    assert "存在" in prompt


def test_build_prompt_omits_reference_note_without_reference(
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
        lambda: {"review_include_package_dir": False},
    )
    monkeypatch.setattr(review_config, "_package_exists_in_repo", lambda _rel: True)
    prompt = build_prompt(
        "main",
        "feature/x",
        ["src/app.py"],
        "diff content without reference",
        "BASE PROMPT",
    )
    assert "注記: vendored パッケージの参照" not in prompt


# ---------------------------
# main() end-to-end with mocked I/O
# ---------------------------


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    """Set up common stubs for git/engine I/O and isolate under tmp_path."""
    monkeypatch.setattr(
        review_config,
        "load_config",
        lambda: {
            "precommit_review_enabled": True,
            "precommit_require_static_checks": True,
        },
    )
    monkeypatch.setattr(precommit_state, "current_branch", lambda: "feature")
    monkeypatch.setattr(precommit_state, "is_valid_branch", lambda _: True)
    monkeypatch.setattr(precommit_review, "_staged_files", lambda: ["foo.py"])
    monkeypatch.setattr(
        precommit_review,
        "_run_static_checks",
        lambda _f: (True, ""),
    )
    monkeypatch.setattr(precommit_review, "_build_diff", lambda *_a: "FAKE DIFF")
    monkeypatch.setattr(precommit_review, "_truncate_diff", lambda d: d)
    # Issue #55 B4: テスト中は実際の git fetch を走らせない。
    monkeypatch.setattr(precommit_review, "_fetch_base_ref", lambda _b: None)

    fake_proj = tmp_path / "proj"
    ame_dir = fake_proj / "ame-ai-review-system"
    ame_dir.mkdir(parents=True)
    (ame_dir / "review_prompt.txt").write_text("PROMPT", encoding="utf-8")
    monkeypatch.setattr(
        precommit_review,
        "_resolve_paths",
        lambda: (ame_dir / "review_prompt.txt", ame_dir / "engine.py"),
    )

    state_path = tmp_path / "state.json"
    monkeypatch.setattr(precommit_state, "state_file_path", lambda: state_path)
    return {"state_path": state_path, "ame_dir": ame_dir}


def _engine_returning(
    monkeypatch: pytest.MonkeyPatch,
    payload_dict: dict[str, Any],
) -> None:
    output = json.dumps(payload_dict)
    monkeypatch.setattr(
        precommit_review,
        "_run_engine",
        lambda _p, _e, _s: (0, output, ""),
    )


def test_main_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        review_config,
        "load_config",
        lambda: {"precommit_review_enabled": False},
    )
    rc = precommit_review.main([])
    assert rc == 0


# ---------------------------
# _run_static_checks
# ---------------------------


def test_run_static_checks_empty_files(monkeypatch: pytest.MonkeyPatch) -> None:
    passed, detail = run_static_checks([])
    assert passed is True
    assert not detail


def test_run_static_checks_precommit_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    passed, detail = run_static_checks(["foo.py"])
    assert passed is True
    assert not detail


def test_run_static_checks_skipped_under_precommit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # pre-commit フレームワーク実行中は実フックが既に強制済みのため二重実行しない。
    monkeypatch.setenv("PRE_COMMIT", "1")
    passed, detail = run_static_checks(["foo.py"])
    assert passed is True
    assert not detail


def _setup_precommit_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    # pytest が pre-commit (pre-push 等) 配下で動くと PRE_COMMIT が設定されるため、
    # 静的チェックの実体が走るようテスト中は除去する。
    monkeypatch.delenv("PRE_COMMIT", raising=False)
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: ruff-check\n"
        "        name: ruff check\n"
        "        entry: ruff check\n"
        "        language: system\n"
        "        types_or: [python]\n"
        "      - id: ai-precommit-review\n"
        "        name: AI review\n"
        "        entry: python3 -m ame_ai_review_system.precommit_review\n"
        "        language: system\n"
        "        always_run: true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/pre-commit")
    monkeypatch.setattr(precommit_state, "run_git", lambda _: f"{proj}\n")
    return proj


def test_run_static_checks_all_pass(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _setup_precommit_project(monkeypatch, tmp_path)
    captured: dict[str, Any] = {}

    def fake_run(cmd: list[str], **_kw: Any) -> SimpleNamespace:
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    passed, detail = run_static_checks(["foo.py"])
    assert passed is True
    assert not detail
    # 実 pre-commit フックを --config + --files で呼んでいること。
    assert captured["cmd"][0] == "/usr/bin/pre-commit"
    assert captured["cmd"][1] == "run"
    assert "--config" in captured["cmd"]
    assert "foo.py" in captured["cmd"]


def test_run_static_checks_fails_on_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _setup_precommit_project(monkeypatch, tmp_path)

    def fake_run(cmd: list[str], **_kw: Any) -> SimpleNamespace:
        return SimpleNamespace(
            returncode=1,
            stdout="E501 line too long",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    passed, detail = run_static_checks(["foo.py"])
    assert passed is False
    assert "pre-commit:" in detail
    assert "E501" in detail


def test_run_static_checks_env_failure_skips(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Issue #55 I2: フック環境のクローン/インストール失敗はコード品質失敗ではなく
    # スキップする (毎コミットの誤ブロック回避)。
    _setup_precommit_project(monkeypatch, tmp_path)

    def fake_run(cmd: list[str], **_kw: Any) -> SimpleNamespace:
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="An error has occurred: Failed to clone "
            "https://github.com/pre-commit/pre-commit-hooks",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    passed, detail = run_static_checks(["foo.py"])
    assert passed is True
    assert not detail


def test_looks_like_env_failure() -> None:
    assert precommit_review._looks_like_env_failure(
        "An error has occurred\nFailed to clone repo"
    )
    assert precommit_review._looks_like_env_failure("could not resolve host github.com")
    assert not precommit_review._looks_like_env_failure("E501 line too long")
    assert not precommit_review._looks_like_env_failure("")


def test_run_static_checks_timeout_skips(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _setup_precommit_project(monkeypatch, tmp_path)

    def fake_run(cmd: list[str], **_kw: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd, 120)

    monkeypatch.setattr(subprocess, "run", fake_run)
    passed, detail = run_static_checks(["foo.py"])
    assert passed is True
    assert not detail


def test_run_static_checks_no_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/pre-commit")
    monkeypatch.setattr(precommit_state, "run_git", lambda _: f"{proj}\n")
    passed, detail = run_static_checks(["foo.py"])
    assert passed is True
    assert not detail


def test_run_static_checks_unparseable_config_skips(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".pre-commit-config.yaml").write_text(
        "{not valid yaml",
        encoding="utf-8",
    )
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/pre-commit")
    monkeypatch.setattr(precommit_state, "run_git", lambda _: f"{proj}\n")
    passed, detail = run_static_checks(["foo.py"])
    assert passed is True
    assert not detail


def test_filtered_precommit_config_removes_ai_hooks() -> None:
    raw: dict[str, Any] = {
        "repos": [
            {
                "repo": "local",
                "hooks": [
                    {"id": "ruff-check", "entry": "ruff check"},
                    {"id": "ai-skip-guard", "entry": "python3 skip_guard"},
                    {"id": "ai-precommit-review", "entry": "python3 precommit_review"},
                    {"id": "ai-review-state-reset", "entry": "python3 reset"},
                ],
            }
        ]
    }
    filtered = precommit_review._filtered_precommit_config(raw)
    ids = [h["id"] for h in filtered["repos"][0]["hooks"]]
    assert ids == ["ruff-check"]


# ---------------------------
# main() — static checks integration
# ---------------------------


@pytest.mark.usefixtures("env")
def test_main_blocks_when_static_checks_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        precommit_review,
        "_run_static_checks",
        lambda _f: (False, "ruff check:\nE501 line too long"),
    )
    monkeypatch.setattr(
        precommit_review,
        "_run_engine",
        lambda _p, _e, _s: (0, '{"summary":"ok","comments":[]}', ""),
    )
    rc = precommit_review.main([])
    assert rc == 1


@pytest.mark.usefixtures("env")
def test_main_hides_engine_banner_when_gate1_false(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Issue #40: show_engine_info_gate1=false でエンジン情報バナーを抑止する。
    monkeypatch.setattr(
        review_config,
        "load_config",
        lambda: {
            "precommit_review_enabled": True,
            "precommit_require_static_checks": False,
            "show_engine_info_gate1": False,
        },
    )
    _engine_returning(monkeypatch, {"summary": "ok", "comments": []})
    rc = precommit_review.main([])
    assert rc == 0
    err = capsys.readouterr().err
    assert "running AI review" not in err


@pytest.mark.usefixtures("env")
def test_main_shows_engine_banner_by_default(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Issue #40: 既定 (gate1 未設定) ではエンジン情報バナーを表示する。
    _engine_returning(monkeypatch, {"summary": "ok", "comments": []})
    rc = precommit_review.main([])
    assert rc == 0
    err = capsys.readouterr().err
    assert "running AI review" in err


@pytest.mark.usefixtures("env")
def test_main_dry_run_static_checks_fail_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        precommit_review,
        "_run_static_checks",
        lambda _f: (False, "ruff check:\nE501"),
    )
    rc = precommit_review.main(["--dry-run"])
    assert rc == 0


@pytest.mark.usefixtures("env")
def test_main_skips_static_checks_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_config,
        "load_config",
        lambda: {
            "precommit_review_enabled": True,
            "precommit_require_static_checks": False,
        },
    )
    called: list[str] = []

    def _fake_static_checks(_f: list[str]) -> tuple[bool, str]:
        called.append("checked")
        return (True, "")

    monkeypatch.setattr(
        precommit_review,
        "_run_static_checks",
        _fake_static_checks,
    )
    _engine_returning(monkeypatch, {"summary": "ok", "comments": []})
    rc = precommit_review.main([])
    assert rc == 0
    assert called == []


@pytest.mark.usefixtures("env")
def test_main_skips_when_no_staged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(precommit_review, "_staged_files", list)
    rc = precommit_review.main([])
    assert rc == 0


@pytest.mark.usefixtures("env")
def test_main_skips_when_detached_head(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(precommit_state, "current_branch", lambda: "HEAD")
    rc = precommit_review.main([])
    assert rc == 0


@pytest.mark.usefixtures("env")
def test_main_skips_when_invalid_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(precommit_state, "current_branch", lambda: "bad branch")
    monkeypatch.setattr(precommit_state, "is_valid_branch", lambda _: False)
    rc = precommit_review.main([])
    assert rc == 0


@pytest.mark.usefixtures("env")
def test_main_blocks_when_engine_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        precommit_review,
        "_run_engine",
        lambda _p, _e, _s: (1, "", "boom"),
    )
    rc = precommit_review.main([])
    assert rc == 1


@pytest.mark.usefixtures("env")
def test_main_dry_run_engine_failure_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        precommit_review,
        "_run_engine",
        lambda _p, _e, _s: (1, "", "boom"),
    )
    rc = precommit_review.main(["--dry-run"])
    assert rc == 0


def test_main_engine_failure_escape_hatch_after_three(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, Any],
) -> None:
    # エンジン失敗が3回連続したら escape hatch で PASS する (LLM API 一時障害対策)。
    # engine_failure_streak は low_only_streak とは独立カウンタ。
    precommit_state.write_state(
        env["state_path"],
        {"branches": {"feature": {"engine_failure_streak": 2}}},
    )
    monkeypatch.setattr(
        precommit_review,
        "_run_engine",
        lambda _p, _e, _s: (1, "", "boom"),
    )
    rc = precommit_review.main([])
    assert rc == 0
    state = precommit_state.read_state(env["state_path"])
    assert state["branches"]["feature"]["engine_failure_streak"] == 3


@pytest.mark.usefixtures("env")
def test_main_blocks_when_engine_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        precommit_review,
        "_run_engine",
        lambda _p, _e, _s: (0, "   ", ""),
    )
    rc = precommit_review.main([])
    assert rc == 1


def test_main_blocks_on_blocking_issue_and_resets_streak(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, Any],
) -> None:
    precommit_state.write_state(
        env["state_path"],
        {"branches": {"feature": {"low_only_streak": 2}}},
    )
    _engine_returning(
        monkeypatch,
        {
            "summary": "blocking",
            "comments": [
                {
                    "path": "foo.py",
                    "line": 1,
                    "severity": "HIGH",
                    "title": "T",
                    "body": "B",
                },
            ],
        },
    )
    rc = precommit_review.main([])
    assert rc == 1
    state = precommit_state.read_state(env["state_path"])
    assert state["branches"]["feature"]["low_only_streak"] == 0


def test_main_passes_on_zero_issues(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, Any],
) -> None:
    _engine_returning(monkeypatch, {"summary": "ok", "comments": []})
    rc = precommit_review.main([])
    assert rc == 0
    state = precommit_state.read_state(env["state_path"])
    assert state["branches"]["feature"]["low_only_streak"] == 0


def test_main_low_only_streak_increments(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, Any],
) -> None:
    _engine_returning(
        monkeypatch,
        {
            "summary": "low only",
            "comments": [
                {
                    "path": "f",
                    "line": 1,
                    "severity": "LOW",
                    "title": "t",
                    "body": "b",
                },
            ],
        },
    )
    rc = precommit_review.main([])
    assert rc == 1
    state = precommit_state.read_state(env["state_path"])
    assert state["branches"]["feature"]["low_only_streak"] == 1


def test_main_low_only_at_threshold_passes(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, Any],
) -> None:
    precommit_state.write_state(
        env["state_path"],
        {"branches": {"feature": {"low_only_streak": 1}}},
    )
    _engine_returning(
        monkeypatch,
        {
            "summary": "low only 2nd",
            "comments": [
                {
                    "path": "f",
                    "line": 1,
                    "severity": "LOW",
                    "title": "t",
                    "body": "b",
                },
            ],
        },
    )
    rc = precommit_review.main([])
    assert rc == 0
    state = precommit_state.read_state(env["state_path"])
    assert state["branches"]["feature"]["low_only_streak"] == 2


def test_main_stale_review_demotes_and_builds_streak(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, Any],
) -> None:
    # Issue #55 B2: 同一指摘の繰り返しは severity が HIGH/MIDDLE に振れても LOW へ
    # 降格され、streak が進む (escape 条件自体は変更しない)。
    payload_dict: dict[str, Any] = {
        "summary": "same issue",
        "comments": [
            {
                "path": "f",
                "line": 1,
                "severity": "MIDDLE",
                "title": "バグが残っています",
                "body": "バグが残っています の詳細",
            },
        ],
    }
    _engine_returning(monkeypatch, payload_dict)
    rc = precommit_review.main([])
    assert rc == 1
    state = precommit_state.read_state(env["state_path"])
    assert state["branches"]["feature"]["low_only_streak"] == 0
    assert len(state["branches"]["feature"]["recent_review_texts"]) == 1

    payload_dict["comments"][0]["severity"] = "HIGH"
    _engine_returning(monkeypatch, payload_dict)
    rc = precommit_review.main([])
    assert rc == 1
    state = precommit_state.read_state(env["state_path"])
    # stale 検出で LOW 扱いになり streak が 1 進む。
    assert state["branches"]["feature"]["low_only_streak"] == 1


def test_main_dry_run_does_not_write_state(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, Any],
) -> None:
    _engine_returning(
        monkeypatch,
        {
            "summary": "low",
            "comments": [
                {
                    "path": "f",
                    "line": 1,
                    "severity": "LOW",
                    "title": "t",
                    "body": "b",
                },
            ],
        },
    )
    rc = precommit_review.main(["--dry-run"])
    assert rc == 0
    assert not env["state_path"].exists()


def test_main_blocks_when_prompt_file_missing(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, Any],
) -> None:
    env["ame_dir"].joinpath("review_prompt.txt").unlink()
    _engine_returning(monkeypatch, {"summary": "", "comments": []})
    rc = precommit_review.main([])
    assert rc == 1


@pytest.mark.usefixtures("env")
def test_main_blocks_on_malformed_engine_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # parse_review_json が fallback した場合は fail-closed でブロックする。
    monkeypatch.setattr(
        precommit_review,
        "_run_engine",
        lambda _p, _e, _s: (0, "not json at all", ""),
    )
    rc = precommit_review.main([])
    assert rc == 1


@pytest.mark.usefixtures("env")
def test_main_blocks_when_comments_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # comments キー自体が無い場合は不正出力としてブロックする (fail-closed)。
    _engine_returning(monkeypatch, {"summary": "LGTM"})
    rc = precommit_review.main([])
    assert rc == 1


@pytest.mark.usefixtures("env")
def test_main_blocks_when_comments_not_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # comments が list でない場合もブロックする。
    _engine_returning(monkeypatch, {"summary": "x", "comments": "not-a-list"})
    rc = precommit_review.main([])
    assert rc == 1


@pytest.mark.usefixtures("env")
def test_main_blocks_on_unknown_severity(monkeypatch: pytest.MonkeyPatch) -> None:
    # 未知 severity (WARNING 等) は fail-closed で blocking 扱い。
    _engine_returning(
        monkeypatch,
        {
            "summary": "warn",
            "comments": [
                {
                    "path": "f",
                    "line": 1,
                    "severity": "WARNING",
                    "title": "t",
                    "body": "b",
                },
            ],
        },
    )
    rc = precommit_review.main([])
    assert rc == 1


# ---------------------------
# post_commit_reset.main()
# ---------------------------


def _enable_post_commit_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    """post_commit_reset は起動時に config を参照するため、テスト毎に有効化する."""
    monkeypatch.setattr(
        review_config,
        "load_config",
        lambda: {"precommit_review_enabled": True},
    )


def test_post_commit_reset_clears_streak(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_post_commit_reset(monkeypatch)
    state_path = tmp_path / "state.json"
    precommit_state.write_state(
        state_path,
        {"branches": {"feature": {"low_only_streak": 2}}},
    )
    monkeypatch.setattr(precommit_state, "current_branch", lambda: "feature")
    monkeypatch.setattr(precommit_state, "is_valid_branch", lambda _: True)
    monkeypatch.setattr(precommit_state, "state_file_path", lambda: state_path)

    rc = post_commit_reset.main()
    assert rc == 0
    state = precommit_state.read_state(state_path)
    assert state["branches"]["feature"]["low_only_streak"] == 0


def test_post_commit_reset_noop_when_invalid_branch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_post_commit_reset(monkeypatch)
    state_path = tmp_path / "state.json"
    precommit_state.write_state(
        state_path,
        {"branches": {"bad name": {"low_only_streak": 2}}},
    )
    monkeypatch.setattr(precommit_state, "current_branch", lambda: "bad name")
    monkeypatch.setattr(precommit_state, "is_valid_branch", lambda _: False)
    monkeypatch.setattr(precommit_state, "state_file_path", lambda: state_path)

    rc = post_commit_reset.main()
    assert rc == 0
    state = precommit_state.read_state(state_path)
    assert state["branches"]["bad name"]["low_only_streak"] == 2


def test_post_commit_reset_noop_when_detached_head(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_post_commit_reset(monkeypatch)
    # detached HEAD (branch == "HEAD") はスキップし、state を書き換えない。
    state_path = tmp_path / "state.json"
    precommit_state.write_state(
        state_path,
        {"branches": {"feature": {"low_only_streak": 2}}},
    )
    monkeypatch.setattr(precommit_state, "current_branch", lambda: "HEAD")
    # is_valid_branch("HEAD") は True になるため、明示的な HEAD チェックが必須。
    monkeypatch.setattr(precommit_state, "is_valid_branch", lambda _: True)
    monkeypatch.setattr(precommit_state, "state_file_path", lambda: state_path)

    rc = post_commit_reset.main()
    assert rc == 0
    state = precommit_state.read_state(state_path)
    # 書き換えられていないこと
    assert state["branches"]["feature"]["low_only_streak"] == 2
    assert "HEAD" not in state["branches"]


def test_post_commit_reset_noop_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # precommit_review_enabled=false なら state を触らない。
    monkeypatch.setattr(
        review_config,
        "load_config",
        lambda: {"precommit_review_enabled": False},
    )
    state_path = tmp_path / "state.json"
    precommit_state.write_state(
        state_path,
        {"branches": {"feature": {"low_only_streak": 2}}},
    )
    monkeypatch.setattr(precommit_state, "current_branch", lambda: "feature")
    monkeypatch.setattr(precommit_state, "is_valid_branch", lambda _: True)
    monkeypatch.setattr(precommit_state, "state_file_path", lambda: state_path)

    rc = post_commit_reset.main()
    assert rc == 0
    state = precommit_state.read_state(state_path)
    assert state["branches"]["feature"]["low_only_streak"] == 2


def test_post_commit_reset_creates_state_if_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_post_commit_reset(monkeypatch)
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(precommit_state, "current_branch", lambda: "feature")
    monkeypatch.setattr(precommit_state, "is_valid_branch", lambda _: True)
    monkeypatch.setattr(precommit_state, "state_file_path", lambda: state_path)

    rc = post_commit_reset.main()
    assert rc == 0
    state = precommit_state.read_state(state_path)
    assert state["branches"]["feature"]["low_only_streak"] == 0
