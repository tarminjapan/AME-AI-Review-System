"""Stale-loop 検出 (同一指摘の繰り返し) の共通実装.

返信判定 (reply.py) と pre-commit / PR streak の escape 判定で共用する。
文字トリグラムの Jaccard 類似度で「直近 2 件のコメント本文が実質同じ」を検出する。
日本語テキストに対応するため単語分割ではなくトリグラムを使用する (Issue #55 B2)。
"""

from __future__ import annotations

from typing import Any

_TRIGRAM_SIZE = 3
_STALE_JACCARD_THRESHOLD = 0.80
_STALE_MIN_NGRAMS = 4
_MIN_COMMENTS_FOR_STALE = 2


def trigrams(text: str) -> set[str]:
    """本文から文字トリグラム集合を抽出する."""
    text = text.lower().strip()
    if len(text) < _TRIGRAM_SIZE:
        return {text} if text else set()
    return {text[i : i + _TRIGRAM_SIZE] for i in range(len(text) - (_TRIGRAM_SIZE - 1))}


def is_stale_loop(
    comment_bodies: list[str],
    *,
    threshold: float | None = None,
) -> bool:
    """直近 2 件の本文が同一指摘の繰り返しか判定する.

    トリグラム数が 4 未満の短いコメントは完全一致で判定する。
    ``threshold`` で Jaccard しきい値を上書きできる (Issue #67)。
    """
    if len(comment_bodies) < _MIN_COMMENTS_FOR_STALE:
        return False

    g1 = trigrams(comment_bodies[-2])
    g2 = trigrams(comment_bodies[-1])

    if not g1 or not g2:
        return False

    if len(g1) < _STALE_MIN_NGRAMS or len(g2) < _STALE_MIN_NGRAMS:
        return g1 == g2

    cutoff = threshold if threshold is not None else _STALE_JACCARD_THRESHOLD
    jaccard = len(g1 & g2) / len(g1 | g2)
    return jaccard >= cutoff


def comment_text(comment: dict[str, Any]) -> str:
    """コメント 1 件の stale-loop 判定用本文を合成する.

    severity は MIDDLE → LOW → MIDDLE と揺れるため比較対象から除外する
    (Issue #55 B2)。

    Issue #67: 指摘の安定識別子である ``path`` / ``line`` / ``title`` を主体にする。
    LLM は修正済みの同一指摘を本文 (body) を言い換えて再投稿するが、トリグラム集合
    は本文の差異で希釈されるため本文を比較に使うと Jaccard が下がり stale 判定が
    発火しない。path/line/title が揃う場合はこれをアンカーとして本文を除外し、
    同一箇所への再投稿を確実に検出する。アンカーが実質的に空 (path も title も
    無い) の場合は本文で比較する。
    """
    path = str(comment.get("path", "")).strip()
    line = comment.get("line", "")
    title = str(comment.get("title", "")).strip()
    if path or title:
        return f"{path}\n{line}\n{title}"
    return str(comment.get("body", ""))


def demote_stale(
    comments: list[dict[str, Any]],
    prev_comment_texts: list[str],
    *,
    threshold: float | None = None,
) -> list[dict[str, Any]]:
    """前回レビューと同一のコメントのみを LOW へ降格する.

    LLM が同じ指摘を MIDDLE → LOW → MIDDLE と severity を揺らすと LOW-only streak が
    進まないため、コメント単位の Jaccard stale-loop 検出で繰り返し指摘だけを LOW 扱いに
    落として escape を機能させる (Issue #55 B2)。

    レビュー全体ではなくコメント単位で突き合わせることで、繰り返し指摘の中に紛れた
    新規の CRITICAL/HIGH 指摘を誤って降格しない。escape 条件自体は変更しない。
    ``threshold`` で Jaccard しきい値を上書きできる (Issue #67)。
    """
    if not prev_comment_texts:
        return comments
    prev_texts = [p for p in prev_comment_texts if p.strip()]
    if not prev_texts:
        return comments
    result: list[dict[str, Any]] = []
    for comment in comments:
        current = comment_text(comment)
        if not current.strip() or not any(
            is_stale_loop([prev, current], threshold=threshold) for prev in prev_texts
        ):
            result.append(comment)
            continue
        result.append({**comment, "severity": "LOW"})
    return result
