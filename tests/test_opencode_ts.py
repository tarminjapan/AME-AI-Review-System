# pyright: basic
from __future__ import annotations

import pytest
from ame_ai_review_system.engines import opencode_ts, ts_runner


@pytest.fixture(autouse=True)
def _no_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    # 実 serve 起動を防ぐ。
    monkeypatch.setattr(opencode_ts, "ensure_opencode_server", lambda: None)


def _capture(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, str, list[str], float]]:
    calls: list[tuple[str, str, list[str], float]] = []

    def fake_run_sidecar(
        script: str,
        prompt: str,
        args: list[str],
        timeout: float,
    ) -> str:
        calls.append((script, prompt, args, timeout))
        return "{}"

    monkeypatch.setattr(ts_runner, "run_sidecar", fake_run_sidecar)
    return calls


def test_run_forwards_thinking_low_as_variant_low(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Issue #137: thinking が opencode の variant として転送されること。
    calls = _capture(monkeypatch)
    opencode_ts.OpencodeTsAdapter.run(
        "prompt",
        {
            "model": "opencode-go/deepseek-v4-flash",
            "thinking": "low",
            "timeout": 600,
        },
    )
    args = calls[0][2]
    assert "--model" in args
    assert "--variant" in args
    assert args[args.index("--variant") + 1] == "low"


def test_run_forwards_thinking_high_as_variant_high(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _capture(monkeypatch)
    opencode_ts.OpencodeTsAdapter.run(
        "prompt",
        {"model": "m/x", "thinking": "high", "timeout": 600},
    )
    args = calls[0][2]
    assert args[args.index("--variant") + 1] == "high"


def test_run_omits_variant_when_thinking_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _capture(monkeypatch)
    opencode_ts.OpencodeTsAdapter.run(
        "prompt",
        {"thinking": "bogus", "timeout": 600},
    )
    assert "--variant" not in calls[0][2]
