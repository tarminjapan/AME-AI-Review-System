# pyright: basic
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ame_ai_review_system import precommit_state

if TYPE_CHECKING:
    import pytest


def test_get_streak_empty_state() -> None:
    assert precommit_state.get_streak({}, "feature") == 0


def test_get_streak_present() -> None:
    state = {"branches": {"feature": {"low_only_streak": 2}}}
    assert precommit_state.get_streak(state, "feature") == 2


def test_get_streak_missing_branch() -> None:
    state = {"branches": {"other": {"low_only_streak": 1}}}
    assert precommit_state.get_streak(state, "feature") == 0


def test_get_streak_invalid_value() -> None:
    state = {"branches": {"feature": {"low_only_streak": "abc"}}}
    assert precommit_state.get_streak(state, "feature") == 0


def test_get_streak_non_dict_branches() -> None:
    state = {"branches": "not-a-dict"}
    assert precommit_state.get_streak(state, "feature") == 0


def test_get_streak_non_dict_entry() -> None:
    state = {"branches": {"feature": "not-a-dict"}}
    assert precommit_state.get_streak(state, "feature") == 0


def test_set_streak_initializes_branches() -> None:
    state: dict[str, object] = {}
    precommit_state.set_streak(state, "feature", 1)
    assert state == {"branches": {"feature": {"low_only_streak": 1}}}


def test_set_streak_preserves_other_branches() -> None:
    state: dict[str, object] = {"branches": {"other": {"low_only_streak": 5}}}
    precommit_state.set_streak(state, "feature", 1)
    branches = state["branches"]
    assert isinstance(branches, dict)
    assert branches["other"]["low_only_streak"] == 5
    assert branches["feature"]["low_only_streak"] == 1


def test_set_streak_custom_key() -> None:
    state: dict[str, object] = {}
    precommit_state.set_streak(state, "feature", 2, key="engine_failure_streak")
    branches = state["branches"]
    assert isinstance(branches, dict)
    assert branches["feature"]["engine_failure_streak"] == 2


def test_get_streak_custom_key() -> None:
    state = {"branches": {"feature": {"engine_failure_streak": 2}}}
    assert (
        precommit_state.get_streak(state, "feature", key="engine_failure_streak") == 2
    )


def test_set_streak_preserves_other_keys_in_same_branch() -> None:
    state: dict[str, object] = {
        "branches": {"feature": {"low_only_streak": 1}},
    }
    precommit_state.set_streak(state, "feature", 2, key="engine_failure_streak")
    branches = state["branches"]
    assert isinstance(branches, dict)
    entry = branches["feature"]
    assert entry["low_only_streak"] == 1
    assert entry["engine_failure_streak"] == 2


def test_reset_all_streaks() -> None:
    state: dict[str, Any] = {
        "branches": {
            "feature": {
                "low_only_streak": 2,
                "engine_failure_streak": 2,
                "total_review_count": 3,
            },
        },
    }
    precommit_state.reset_all_streaks(state, "feature")
    entry = state["branches"]["feature"]
    assert entry["low_only_streak"] == 0
    assert entry["engine_failure_streak"] == 0
    assert entry["total_review_count"] == 0


def test_recent_reviews_roundtrip() -> None:
    state: dict[str, Any] = {}
    precommit_state.set_recent_reviews(state, "feature", ["a", "b", "c"])
    assert precommit_state.get_recent_reviews(state, "feature") == ["a", "b", "c"]


def test_recent_reviews_empty_state() -> None:
    assert precommit_state.get_recent_reviews({}, "feature") == []
    assert precommit_state.get_recent_reviews({"branches": {}}, "feature") == []
    assert (
        precommit_state.get_recent_reviews(
            {"branches": {"other": {"recent_review_texts": ["x"]}}},
            "feature",
        )
        == []
    )


def test_recent_reviews_ignores_non_string() -> None:
    state = {"branches": {"feature": {"recent_review_texts": ["a", 1, None]}}}
    assert precommit_state.get_recent_reviews(state, "feature") == ["a"]


def test_reset_all_streaks_clears_recent_reviews() -> None:
    state: dict[str, Any] = {
        "branches": {
            "feature": {
                "low_only_streak": 2,
                "recent_review_texts": ["previous review"],
            },
        },
    }
    precommit_state.reset_all_streaks(state, "feature")
    entry = state["branches"]["feature"]
    assert entry["low_only_streak"] == 0
    assert entry["recent_review_texts"] == []


def test_last_fetched_head_roundtrip() -> None:
    state: dict[str, Any] = {}
    assert not precommit_state.get_last_fetched_head(state)
    precommit_state.set_last_fetched_head(state, "abc123")
    assert precommit_state.get_last_fetched_head(state) == "abc123"
    state = {"last_fetched_head": 123}
    assert not precommit_state.get_last_fetched_head(state)


def test_set_streak_overwrites_same_branch() -> None:
    state: dict[str, object] = {"branches": {"feature": {"low_only_streak": 5}}}
    precommit_state.set_streak(state, "feature", 0)
    branches = state["branches"]
    assert isinstance(branches, dict)
    assert branches["feature"]["low_only_streak"] == 0


def test_set_streak_replaces_non_dict_branches() -> None:
    state: dict[str, object] = {"branches": "garbage"}
    precommit_state.set_streak(state, "feature", 1)
    assert state == {"branches": {"feature": {"low_only_streak": 1}}}


def test_write_read_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = {"branches": {"feature": {"low_only_streak": 2}}}
    precommit_state.write_state(path, state)
    loaded = precommit_state.read_state(path)
    assert loaded == state


def test_read_state_missing_file(tmp_path: Path) -> None:
    assert precommit_state.read_state(tmp_path / "missing.json") == {}


def test_read_state_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("not json {{{", encoding="utf-8")
    assert precommit_state.read_state(path) == {}


def test_read_state_non_dict_root(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert precommit_state.read_state(path) == {}


def test_write_state_creates_parent_dirs(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "deep" / "state.json"
    precommit_state.write_state(path, {"branches": {}})
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == {"branches": {}}


def test_write_state_leaves_no_temp_files(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    precommit_state.write_state(path, {"branches": {"feature": {"low_only_streak": 1}}})
    # atomic write 完了後は一時ファイルが残らないこと
    leftover = list(tmp_path.glob(".precommit_state_*.tmp"))
    assert leftover == []


def test_write_state_replaces_existing(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    precommit_state.write_state(path, {"branches": {"a": {"low_only_streak": 1}}})
    precommit_state.write_state(path, {"branches": {"b": {"low_only_streak": 2}}})
    state = precommit_state.read_state(path)
    assert "a" not in state["branches"]
    assert state["branches"]["b"]["low_only_streak"] == 2


def test_is_valid_branch_valid() -> None:
    assert precommit_state.is_valid_branch("main")
    assert precommit_state.is_valid_branch("feature/foo")
    assert precommit_state.is_valid_branch("feature-foo.bar_baz")
    assert precommit_state.is_valid_branch("release/1.0")


def test_is_valid_branch_invalid() -> None:
    assert not precommit_state.is_valid_branch("")
    assert not precommit_state.is_valid_branch("a b c")
    # シェルインジェクション防止
    assert not precommit_state.is_valid_branch("feature; rm -rf /")
    assert not precommit_state.is_valid_branch("feature$(cmd)")
    assert not precommit_state.is_valid_branch("feature`cmd`")


def test_state_file_path_uses_remote(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_git(args: list[str]) -> str:
        if args == ["remote", "get-url", "origin"]:
            return "https://example.com/owner/repo.git\n"
        return ""

    monkeypatch.setattr(precommit_state, "run_git", fake_git)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    path = precommit_state.state_file_path()
    assert path.parent == tmp_path / ".config" / "ame-ai-review-system"
    assert path.name.startswith("precommit_state_")
    assert path.name.endswith(".json")


def test_state_file_path_falls_back_to_toplevel(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # リモート未設定の場合はトップレベルパスを識別子に使う。
    # state_file_path はパス計算のみで副作用 (mkdir) を持たない。
    def fake_git(args: list[str]) -> str:
        if args == ["remote", "get-url", "origin"]:
            return ""
        if args == ["rev-parse", "--show-toplevel"]:
            return "/home/user/repo\n"
        return ""

    monkeypatch.setattr(precommit_state, "run_git", fake_git)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    path = precommit_state.state_file_path()
    # パス形式のみ検証 (mkdir は write_state 側で行う)
    assert path.parent == tmp_path / ".config" / "ame-ai-review-system"
    assert path.name.startswith("precommit_state_")


def test_state_file_path_stable_for_same_remote(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_git(args: list[str]) -> str:
        if args == ["remote", "get-url", "origin"]:
            return "https://example.com/owner/repo.git\n"
        return ""

    monkeypatch.setattr(precommit_state, "run_git", fake_git)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    p1 = precommit_state.state_file_path()
    p2 = precommit_state.state_file_path()
    assert p1 == p2
