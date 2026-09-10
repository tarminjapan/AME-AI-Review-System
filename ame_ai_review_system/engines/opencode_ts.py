"""OpenCode SDK (TypeScript) サイドカーアダプタ。."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from . import ts_runner
from .errors import FatalEngineError

_DEFAULT_OPENCODE_URL = "http://127.0.0.1:4096"

# thinking (low/medium/high) → opencode の variant。variant は opencode 側で
# reasoning_effort に対応し、モデルが対応しない variant 名はサーバー既定へ倒れる。
# Issue #137: この転送が無いと thinking が SDK に全く届かず (#107 の既定 low 化が
# no-op になる)、reasoning 予算枯渇 (finish=length) を防げない。
_OPENCODE_VARIANT: dict[str, str] = {"low": "low", "medium": "medium", "high": "high"}

# 自動スポーンした serve のレディネス待ち最大秒数。起動直後のモデルコールド
# スタートや LSP 初期化でヘッダー到達まで時間がかかる場合があるため余裕を持つ。
_SERVER_READY_TIMEOUT_SECONDS = 20.0

# ポート疎通確認のポーリング間隔。
_POLL_INTERVAL_SECONDS = 0.5

# serve の疎通確認タイムアウト。
_SERVER_PROBE_TIMEOUT_SECONDS = 1.0

# 意図的にデタッチで残す serve プロセスのハンドル。参照を保持しないと GC 時に
# ResourceWarning (subprocess is still running) が出るため、プロセス終了まで参照する。
_spawned_servers: list[subprocess.Popen[bytes]] = []


class OpencodeServerError(FatalEngineError):
    """``opencode serve`` の起動・接続に関する致命的エラー (Issue #113)."""


def _opencode_url() -> str:
    return os.environ.get("OPENCODE_URL", _DEFAULT_OPENCODE_URL)


def _url_parts(url: str) -> tuple[str, int] | None:
    """URL から (host, port) を返す。パース不能時は None."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if not parsed.hostname:
        return None
    return parsed.hostname, (parsed.port or (80 if parsed.scheme == "http" else 443))


def _is_localhost(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "::1"}


def _server_reachable(host: str, port: int) -> bool:
    """Opencode サーバーが HTTP 応答できるかを判定する (Issue #113).

    単なる TCP 疎通だけだと、他プロセスがポートを占有していても「起動済み」と
    誤判定して自動スポーンをスキップしてしまう。GET / の HTTP 応答ヘッダ
    (``HTTP/`` 始まり) が返るまでをレディネスとみなす。
    """
    try:
        with socket.create_connection(
            (host, port),
            timeout=_SERVER_PROBE_TIMEOUT_SECONDS,
        ) as sock:
            sock.settimeout(_SERVER_PROBE_TIMEOUT_SECONDS)
            sock.sendall(
                b"GET / HTTP/1.0\r\nHost: " + host.encode("ascii") + b"\r\n\r\n",
            )
            return sock.makefile("rb").readline().startswith(b"HTTP/")
    except OSError:
        return False


def _find_opencode_bin() -> str | None:
    return shutil.which("opencode")


def _spawn_server(host: str, port: int) -> None:
    """``opencode serve`` をデタッチ起動し、レディネスまで待つ (Issue #113).

    ローカル Gate 1 は serve 未起動だと ECONNREFUSED で fail-closed になる。
    アダプタ側で自動起動することで「コミットのたびに serve 再起動」という
    運用負荷と原因特定の手間を解消する。外部管理の OPENCODE_URL (リモート)
    には介入しない (呼び出し側の _ensure_opencode_server で localhost 限定)。
    レディネスは OPENCODE_URL の host/port への疎通で判定する。
    """
    opencode_bin = _find_opencode_bin()
    if opencode_bin is None:
        msg = (
            "[engine] opencode CLI not found on PATH. "
            "自動起動には opencode のインストールが必要です。"
            "インストール後に `opencode serve --port "
            f"{port}` を起動するか、再実行してください (Issue #113)。"
        )
        raise OpencodeServerError(msg)
    log_path = Path(tempfile.gettempdir()) / "opencode-ame-review-serve.log"
    try:
        log_file = log_path.open("ab")
    except OSError as exc:
        msg = f"[engine] failed to open serve log {log_path}: {exc}"
        raise OpencodeServerError(msg) from exc
    try:
        proc = subprocess.Popen(
            [opencode_bin, "serve", "--port", str(port)],
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        log_file.close()
        msg = f"[engine] failed to spawn opencode serve: {exc}"
        raise OpencodeServerError(msg) from exc
    # プロセス終了まで参照を保持して GC を防ぐ (意図的なデタッチ)。
    _spawned_servers.append(proc)
    deadline = time.monotonic() + _SERVER_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if _server_reachable(host, port):
            log_file.close()
            return
        if proc.poll() is not None:
            break
        time.sleep(_POLL_INTERVAL_SECONDS)
    # 起動プロセスの失敗 (EADDRINUSE 等) や一時的な未応答でも、既存サーバーが
    # 立ち上がっている場合はそれを利用する (Issue #113)。
    if _server_reachable(host, port):
        log_file.close()
        return
    log_file.close()
    # レディネスに達しなかった serve を放置しない (失敗プロセスを終了させる)。
    proc.terminate()
    msg = (
        f"[engine] opencode serve (port {port}) の起動を待てませんでした。"
        f"ログを確認してください: {log_path} (Issue #113)"
    )
    raise OpencodeServerError(msg)


def _in_ci() -> bool:
    return os.environ.get("GITHUB_ACTIONS") == "true"


def ensure_opencode_server() -> None:
    """サーバーが未起動なら自動スポーンする (Issue #113).

    OPENCODE_URL が localhost を指す場合のみ介入する。CI (GitHub Actions) は
    reusable workflow が serve を明示起動するため、自動スポーンは行わない
    (二重起動によるポート競合を防ぐ)。リモートの OpenCode サーバーも対象外。
    """
    if _in_ci():
        return
    parts = _url_parts(_opencode_url())
    if parts is None:
        return
    host, port = parts
    if not _is_localhost(host):
        return
    if _server_reachable(host, port):
        return
    _spawn_server(host, port)


class OpencodeTsAdapter:
    """バンドル ``engines/ts/opencode.mjs`` 経由で ``@opencode-ai/sdk`` を呼ぶアダプタ。."""

    @staticmethod
    def run(prompt: str, settings: dict[str, Any]) -> str:
        """プロンプトを opencode.mjs サイドカーへ渡し、結果テキストを返す。."""
        # Issue #113: serve 未起動なら自動起動してから接続する。
        ensure_opencode_server()
        args: list[str] = []
        if settings.get("model"):
            args.extend(["--model", str(settings["model"])])
        variant = _OPENCODE_VARIANT.get(str(settings.get("thinking", "low")))
        if variant:
            args.extend(["--variant", variant])
        return ts_runner.run_sidecar(
            "opencode.mjs", prompt, args, float(settings["timeout"])
        )
