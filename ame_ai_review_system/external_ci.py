"""External CI gate helper for Gate 2 (Issue #140).

`/request-review` (Gate 2) は従来、リポジトリ自身の push/PR トリガー CI の合否を
見ずに AI レビューを実行していた。本モジュールは、対象コミット (HEAD SHA) の
check runs から失敗中の外部 CI を検出する純ロジックを提供する (I/O なし)。
"""

from __future__ import annotations

from typing import Any, cast

# GitHub Checks API の conclusion のうち「失敗扱い」とする終端値。skipped / neutral は
# 失敗ではない (skipped はレビュアー自身のジョブの if 判定で発生し得る)。startup_failure は
# ワークフロー自体が起動に失敗した終端状態で、これも失敗として扱う。
FAILING_CONCLUSIONS = frozenset(
    {
        "failure",
        "cancelled",
        "timed_out",
        "action_required",
        "stale",
        "startup_failure",
    },
)


def is_self_check(run: dict[str, Any], reviewer_name: str) -> bool:
    """レビュアー自身の check run か判定する.

    GitHub Actions が作る check run は ``app`` が ``github-actions`` のため、レビュアー
    自身のワークフローとリポジトリの CI を App 単位では区別できない。レビュアーの job 名
    は規約上 reviewer_name を含む (例: "reply / General Review Reply (ame-ai-reviewer)")
    ため、名前の部分一致でも除外する。App slug が reviewer_name と一致する場合
    (App が直接 check run を作る連携) も併せて自身と見なす。
    """
    if not reviewer_name:
        return False
    app = run.get("app")
    if isinstance(app, dict):
        app_dict: dict[str, Any] = cast("dict[str, Any]", app)
        if app_dict.get("slug") == reviewer_name:
            return True
    return reviewer_name in str(run.get("name") or "")


def failing_external_checks(
    check_runs: list[dict[str, Any]],
    reviewer_name: str,
) -> list[str]:
    """失敗中の外部 CI チェック名を昇順で返す (レビュアー自身のジョブは除外).

    未完了のチェック (conclusion が None = queued / in_progress) は失敗扱いしない。
    外部 CI の完了を待たずにレビューを開始できるようにする意図的な fail-open で、
    CI 未完了でゲートを閉じると /request-review が無期限に遅延し得るため。
    """
    failing: set[str] = set()
    for run in check_runs:
        name = str(run.get("name") or "")
        if not name or is_self_check(run, reviewer_name):
            continue
        conclusion = run.get("conclusion")
        if conclusion is not None and str(conclusion) in FAILING_CONCLUSIONS:
            failing.add(name)
    return sorted(failing)
