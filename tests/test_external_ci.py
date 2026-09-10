"""Unit tests for the external CI gate logic (Issue #140)."""

from __future__ import annotations

from typing import Any

from ame_ai_review_system import external_ci


def _run(name: str, conclusion: str | None) -> dict[str, Any]:
    return {"name": name, "conclusion": conclusion}


def test_detects_failure() -> None:
    runs = [
        _run("backend", "success"),
        _run("typegen-check", "failure"),
        _run("e2e", "success"),
    ]
    assert external_ci.failing_external_checks(runs, "ame-ai-reviewer") == [
        "typegen-check"
    ]


def test_ignores_self_runs() -> None:
    runs = [
        _run("reply / General Review Reply (ame-ai-reviewer)", "failure"),
        _run("backend", "success"),
    ]
    assert external_ci.failing_external_checks(runs, "ame-ai-reviewer") == []


def test_ignores_self_run_by_app_slug() -> None:
    # job 名に reviewer_name が含まれなくても app.slug で自身を除外できる (Gate 1 指摘)。
    runs: list[dict[str, Any]] = [
        {"name": "review", "conclusion": "failure", "app": {"slug": "ame-ai-reviewer"}},
        _run("backend", "success"),
    ]
    assert external_ci.failing_external_checks(runs, "ame-ai-reviewer") == []


def test_empty_reviewer_name_does_not_exclude_all() -> None:
    # reviewer_name 未設定 (空文字) でも全チェックを「自身」扱いで除外しない (Gate 1 指摘)。
    runs = [_run("typegen-check", "failure")]
    assert external_ci.failing_external_checks(runs, "") == ["typegen-check"]


def test_ignores_non_failing_conclusions() -> None:
    runs = [
        _run("backend", "success"),
        _run("frontend", "skipped"),
        _run("e2e", "neutral"),
        _run("publish", None),  # in_progress
    ]
    assert external_ci.failing_external_checks(runs, "ame-ai-reviewer") == []


def test_counts_all_failing_conclusions() -> None:
    runs = [
        _run("backend", "cancelled"),
        _run("frontend", "timed_out"),
        _run("e2e", "action_required"),
        _run("lint", "stale"),
        _run("deploy", "startup_failure"),
    ]
    assert external_ci.failing_external_checks(runs, "ame-ai-reviewer") == [
        "backend",
        "deploy",
        "e2e",
        "frontend",
        "lint",
    ]


def test_empty_runs() -> None:
    assert external_ci.failing_external_checks([], "ame-ai-reviewer") == []
