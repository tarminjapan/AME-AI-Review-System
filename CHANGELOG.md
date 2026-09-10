# Changelog

本プロジェクトの主な変更点。形式は [Keep a Changelog](https://keepachangelog.com/)、バージョンは
[Semantic Versioning](https://semver.org/) に準拠。

## [Unreleased]

## [0.2.13] - 2026-09-10

### Fixed

- Gate 1 (pre-commit) が `finish=length`
  空応答でも、fail-closed ではなく自動回復するようにした (Issue #137)。
  - 従来 `--model` しか渡さなかったため opencode では no-op だった既定 low を、`thinking`
    から variant へ実転送して効くようにした。
  - `opencode.mjs` が `finish=length` かつ `output=0`
    を検出したら、variant を high→medium→low と下げて最大 2 回リトライする。最低段では同じ variant で再試行し、モデルの非決定性による回復を狙う。
  - 新設
    `include_branch_diff`（既定 false）でブランチ累積差分をプロンプトから除外する。ステージ済み差分と重複しやすいため reasoning 予算枯渇の一因だった。必要な場合のみ config で true にする。

## [0.2.12] - 2026-09-10

### Fixed

- Gate 1 (pre-commit) に「重大度によらない総レビュー回数のハード上限」を実装した (Issue #134)。
  - `precommit_review._decide` を Gate
    2 と対称な 2 つの独立 escape 機構へ変更。LOW/INFO のみ連続の escape 閾値は固定 2 回（`review_config.LOW_STREAK_THRESHOLD`
    として Gate 1 / Gate 2 で共有）。
  - `precommit_max_reviews`（既定 3 回）は重大度によらない総ラウンド数上限として独立に働く。blocking 指摘（MIDDLE 以上）が残っていても上限到達時にコミットを許可し、警告を出力する（無限ループ防止）。
  - `precommit_max_reviews` が LOW 連続閾値以下（1〜2）の場合は `3`
    にクランプし、blocking 指摘の早期通過を防止。
  - pre-commit state に `total_review_count` を追加（post-commit でリセット）。

## [0.2.11] - 2026-09-09

### Fixed

- ドキュメント・ランディングページを v0.2.10 の実装と整合させた（ドキュメントのみの変更。コード動作は不変）。
  - ランディングページの PR レビュー回数「最大 10 回」を `pr_max_reviews`（既定 3 回）へ修正。Gate
    1 の LOW / INFO escape も `precommit_max_reviews`（既定 3 回）に合わせた。
  - README / docs / ランディングの「LOW / INFO」表記を実装（`precommit_review.py` の
    `_LOW_SEVERITIES`）に合わせて統一。
  - `setup.md` / `customization.md` の JSON 修復回数を最大 3 回（`review_repair_attempts`
    既定 3）へ修正。
  - README・ランディングに「最大ラウンド制限」「グローバル設定」などの欠落機能と設定キーを追記。
  - ランディングのバージョンバッジを v0.2.11 へ更新。

## [0.2.10] - 2026-09-09

### Added

- AI レビュー回数（無限レビュー防止）の上限を Gate 1 / Gate 2 で個別に設定可能にした (Issue
  #129)。`precommit_max_reviews`（既定 3 回）は Gate 1 の LOW/INFO のみ連続 escape 閾値、
  `pr_max_reviews`（既定 3 回）は Gate 2 の総レビュー回数ハード上限。いずれも `config.json`
  で設定し、`0` 以下・不正値は既定 `3` へフォールバックする。
- Gate
  2 の上限到達後は、PR へ一度だけ「レビュー回数上限に達しました」という通知コメントを投稿する (Issue
  #129)。対象 PR スコープのページング走査で重複投稿を防止する。

### Changed

- Gate 2 の総レビュー回数上限を従来の固定 `10` 回から `pr_max_reviews`（既定 3 回）に変更 (Issue
  #129)。
- 収束シグナルの発火ラウンドを 3 から 2 に変更し、`pr_max_reviews=3`
  の最終レビューでも発火するようにした (Issue #129)。

## [0.2.9] - 2026-09-02

### Fixed

- `precommit_engine: "auto"` がグローバル設定の具体エンジンを覆ってしまい、グローバル設定由来の
  `precommit_model` と分裂した無効な組み合わせ（例: `engine=claude` +
  `model=opencode-go/...`）で Gate 1 がクラッシュする問題を解消した (Issue
  #126)。エンジンもモデルと同じ優先順位（リポジトリ設定 > グローバル設定 > 自動検出）で解決する。
- グローバル設定のレガシー `engine` キーもエンジン解決に取り込む。リポジトリ設定に
  `precommit_engine: "auto"` とレガシー `engine` が併存する場合は後者が優先される (Issue #126)。

## [0.2.8] - 2026-08-30

### Added

- Gate 1
  (pre-commit) のエンジン・モデル・思考量をユーザー単位のグローバル設定で指定可能にした (Issue
  #120)。
- 設定ファイル:
  `~/.config/ame-ai-review-system/config.json`。優先順位は 環境変数 > リポジトリ設定 > グローバル設定 > 継承 (自動検出)。
- `ame-ai-reviewer init --engine claude|antigravity` で Python SDK を自動追加する (Issue #114)。
- 対象は pre-commit の `additional_dependencies`。`claude` なら `claude-agent-sdk`、 `antigravity`
  なら `google-antigravity` を追加する。

### Fixed

- `init` 生成の `review_prompt.txt` をパッケージ同梱版へ一元化した。旧版テンプレートが残ると
  `paths.prompt_path()` が弱い出力契約の生成物を優先する問題があった (Issue #111)。
- コードフェンスのサニタイズを、視覚的に似た U+201E から非リテラル風トークン `<FENCE>`
  へ変更した (Issue #112)。LLM レビュアーの false positive (実ファイルの誤検出) を防止する。
- opencode エンジンのローカル Gate
  1 で、serve 未起動やタイムアウトによりコミットがブロックされる問題を解消した (Issue #113)。
- `OPENCODE_URL`
  が localhost なら serve を自動起動する。接続エラー時はバックオフ付きでリトライする。
- `requirements-dev.txt`
  の ruff を 0.16.1 にピンし、CI の preview ルールドリフトによる既存コードの検出失敗を解消。

### Docs

- 返信ワークフローへの `concurrency` 設定禁止と対策を明記 (Issue #115)。
- CI ワークフロー差し替え時の chicken-and-egg 対策を明記した (Issue #116)。
- `issue_comment` は default ブランチ、`pull_request_review_comment`
  は PR ヘッドブランチの workflow が実行される。この非対称性への対策を追記した。
- 対策: ブートストラップ PR、`workflow_dispatch --ref` での明示起動。

## [0.2.7] - 2026-08-20

### Fixed

- Gate 1 (pre-commit) の AI レビューが既定 `thinking=high`
  で動作する問題を修正。差分の大きいコミットでモデルの reasoning 予算を使い切り、`finish=length`
  の空応答となって fail-closed でコミットがブロックされていた。Gate 1 (`thinking`) と Gate
  2 レビュー (`review_thinking`) の既定値を `low` に引き下げた。返信判定の `reply_thinking` は元々
  `low` のため変更なし。これにより reasoning 予算の枯渇を起こしにくくした (Issue #107)。

## [0.2.6] - 2026-08-15

### Fixed

- CI 側 Gate 2 レビューが org 移転後の reusable workflow 参照解決と `workflow_dispatch` の
  `pr_number` 型検証（`Unexpected value '9'`）で失敗する問題。reusable
  workflow（`review-command.yml` / `review-reply.yml`）の `pr_number` / `comment_id` 入力を
  `type: string` に緩和し、配布先ラッパが `fromJSON()` に依存しなくても issue_comment /
  workflow_dispatch の両経路で動作するよう修正 (Issue
  #104)。あわせて旧 org 名 (`tarminjapan/`) の残存参照を棚卸しし、ソース上の残り 1 箇所（`.claude/skills/review-round/SKILL.md`）を
  `AME-Team` に修正。setup.md に両経路の動作検証手順と不正入力時の挙動を追記。

## [0.2.5] - 2026-08-14

### Fixed

- `reply.py`
  が PAT 運用でレビュアー自身の返信を認識できず、スレッドが pending のまま重複 LGTM が投稿される可能性。`github_client.reviewer_logins()`
  で実投稿者 login を解決し、bot login との和集合で照合するよう修正 (Issue #92)。
- レビュー JSON のコメントが `line: null` や非整数を出力すると `build_review_payloads`
  が例外を投げ、ラウンド全体が失敗する問題。`line`
  を検証し、不正値は body-only コメントへフォールバックするよう修正 (Issue #93)。
- `cmd_review` / `reply` の親プロセス `subprocess.run` が `timeout=600` 固定で
  `REVIEW_TIMEOUT_SECONDS` 設定が反映されない問題。`engine.resolve_timeout()`
  で解決した値を渡すよう修正 (Issue #94)。
- `cmd_checkout` が `git fetch` / `git checkout` の失敗を握り潰して exit
  0 を返し、誤ったブランチでレビューが走る問題。成否を検証して失敗時はエラー終了し、`head_branch` も
  `base_ref` と同基準のバリデーションを追加 (Issue #95)。
- `mermaid_check`
  がダブルクォート済みノードラベル（`A["text (parens)"]`）を括弧・波括弧の誤検知でブロックする問題。クォート済みラベルをチェック対象外に修正 (Issue
  #96)。
- `pr_streak._token()` が CI で設定される `AME_AI_REVIEWER_TOKEN`
  を読めず、streak 判定が CI 上で常に無効だった問題。`REVIEWER_TOKEN` / `AME_AI_REVIEWER_TOKEN`
  の両方をフォールバックで読むよう修正 (Issue #97)。

### Gate 1 レビュー指摘への対応 (本 PR 内)

- `reviewer_logins()`
  の実投稿者解決 (`GET /user`) を**成功時のみ**キャッシュ化し、スレッド毎の多重 API 呼び出しを排除。一時的な API 失敗はキャッシュせず再解決できるようにし、失敗固定で Issue
  #92 が再発するのを防ぐ。
- `head_branch` のバリデーションを `[A-Za-z0-9/_.-]` の過剰制限から git
  refname 規約 (`git check-ref-format` 相当) へ変更。`@` / `#` / `+` 等を含む有効なブランチ名 (例:
  `hotfix#123`) を拒否しないよう修正し、先頭ドット・`..`・`@{`・空白等を拒否。
- `_coerce_line` に `inf` / `nan` ガード (`math.isfinite`) を追加。JSON の `1e999` や `"inf"`
  経由の例外 (OverflowError / ValueError) を防ぐ。

### Gate 2 レビュー指摘への対応 (本 PR 内)

- `_run_git_check` の既定タイムアウトは従来どおり 30 秒を維持。大規模になり得る `git fetch` のみ
  `GIT_TIMEOUT_SECONDS` (既定 300) で制御可能にし、checkout 失敗の誤判定を防ぐ。
- `_is_valid_ref_name` の許容文字を git refname 規約 (`git check-ref-format`) に合わせて `(`, `)`,
  `%`, `,`, `{`, `}`, `;`, `$`
  等へ拡張。subprocess はリスト引数のためシェルインジェクションの懸念がなく、有効なブランチ名 (例:
  `fix(issue)`) を拒否しない。
- `reviewer_logins()` の `GET /user`
  について、恒久的不許可 (401、App トークン) はキャッシュして無駄な API 呼び出しを抑止。一時障害 (5xx
  / レート制限 403) は従来どおりキャッシュしない。
- `GIT_TIMEOUT_SECONDS` に `math.isfinite` ガードを追加し、`inf` / `nan`
  を既定 300 へフォールバック。subprocess のタイムアウトで OverflowError が誘発されるのを防ぐ。
- `_is_valid_ref_name`
  の結果は必ず subprocess のリスト引数 (シェル境界を通らない) で渡すというセキュリティ契約を
  `_git_ref_check`
  へ集約。検証済み ref から args を内部生成し、呼び出し側の二重管理による乖離を防ぐ。
- `reviewer_logins`
  が 401 を恒久失敗としてキャッシュする際に警告を一度だけ出力し、PAT の誤設定が無言で `[bot]`
  固定照合へ退行するのを検知可能にする。
- `_is_valid_ref_name` にコンポーネント単位の規約 (`feature/.bar` /
  `feature/foo.lock`) と先頭ハイフン (オプション注入対策) の明示的な拒否を追加し、`git check-ref-format`
  との乖離を縮小。全体の先頭ドットは既存の先頭文字検査に一本化して重複を除去。
- `reviewer_logins` の各テストで一意のトークンを使い、共有キャッシュ由来の実行順依存を排除。

## [0.2.4] - 2026-08-10

### Fixed

- `ame-ai-reviewer init` が生成する `.pre-commit-config.yaml`
  に開発者固有の Python 絶対パスが埋め込まれていた。生成物の共有・コミット時に他環境/CI で失敗する問題を解消。既定を
  `language: python` + `additional_dependencies` に変更し、wheel URL と `#sha256=`
  固定で参照する方式とした。pre-commit が各環境で venv を自動作成する。 `--python` /
  `AME_INIT_PYTHON` 指定時のみオフライン向けの `language: system` で生成 (Issue #79)。
- init が wheel の `#sha256=` をピン留めしない供給チェーンリスク。生成時に GitHub Release
  API から sha256 ダイジェストを解決して URL へ固定。解決できない場合は警告して `#sha256=`
  なしで生成 (Issue #84)。
- codespell exclude から `.ame-review/engines-ts/` の除外が脱落した回帰 (Issue #80)。
- `review_command` wrapper の if と `is-review-command`
  パーサーが不整合だった。改行区切りコマンド（`/request-review\n<理由>`）が静かに skipped される問題を解消。wrapper を軽量な前置フィルタに変更した。厳密判定は reusable ワークフローのパーサーへ一本化 (Issue
  #81)。
- 生成する pre-commit config に `default_install_hook_types` が無い問題。 `pre-commit install`
  だけでは post-commit フック（streak リセット）が導入されなかった。 `[pre-commit, post-commit]`
  を明示し、既存クローン向けの再実行手順を README に追記 (Issue #82)。
- 返信判定モデルが diff に無いファイルの存在を捏造し、同じ指摘を繰り返す stale-loop。返信プロンプトに「diff から確認できないファイルの存在・非存在は断定しない」指示を追加。同一スレッドの連続 non-LGTM 返信（既定 3 回）でも強制 LGTM する判定を追加 (Issue
  #83)。

### Changed

- README / セットアップガイドのクイックスタートに、`uv tool install`
  での導入手順を追加（pipx と同等の CLI ツール管理）(Issue #85)。

## [0.2.3] - 2026-08-09

### Added

- `ame-ai-reviewer init` に TypeScript 向け preset (`ts`) と `--preset auto` を追加。
  `package.json` + `.ts`/`.tsx` ソースの有無で `ts` / `full` を自動選択し、Python 主体で
  `package.json` が付随するリポジトリでも Python ゲート (ruff/mypy) を消さない (Issue #69)。
- 生成する `.pre-commit-config.yaml` で lockfile を codespell / yamllint /
  prettier から自動除外 (Issue #69)。

### Fixed

- `workflow_dispatch` 時に `command` が空になり手動実行でレビュー判定が通らない問題。
  `command: comment.body || '/request-review'` でフォールバック (Issue #71)。
- `review_command` ラッパが `/request-review`
  以外のスラッシュコメントでも発火する問題。コマンド判定を完全一致 / 空白区切りの引数付きに限定 (Issue
  #70)。
- Issue へのコメントで `review_command`
  が発火し skipped ランがノイズになる問題。concurrency グループ化で抑制 (Issue #68)。
- PEP 668 (externally-managed) 環境で Gate 1 の pre-commit AI フックが動作しない問題。 `--python` /
  `AME_INIT_PYTHON` / `sys.executable` の順でインタープリタを自動検出して `entry:`
  に埋め込み、import 可能性を検証 (Issue #66)。
- AI レビュー出力の JSON パース失敗でラウンド全体が失敗する問題。修復試行回数をパラメータ化 (`review_repair_attempts`) し、パース失敗時は
  `reviewed-sha` マーカーを付与せず再レビュー可能にした。プロンプトでも JSON 出力を強制 (Issue
  #65)。
- 修正済み指摘の再投稿で stale-loop 検出が発火しない問題。`path`/`line`/`title` のアンカー一致 +
  severity ガードで再投稿を検出しつつ、HIGH/CRITICAL の過降格を防止 (Issue #67)。

### Changed

- `init` が生成する Gate 1 フックの `entry:`
  を実インタープリタパス埋め込み方式へ変更。パスに空白が含まれる場合は警告 (Issue #66)。

## [0.2.2] - 2026-08-06

### Fixed

- Gate 1 (pre-commit)・Gate 2 (PRレビュー) ともに差分が 4000 行を超えると前方のみを保持し、
  `index.css` / `types/` / `views/` / `tests/`
  等の後方ファイルがレビュー対象から消失して「定義が見当たらない」MIDDLE/HIGH 誤指摘が連発する問題を、優先度付き切り捨てで恒久対応 (Issue
  #62)。
  - 共通モジュール `diff_truncate.py`
    を新設。`priority`（優先セクション全行保持 + コンテキスト末尾保持）/
    `front`（従来）の 2 戦略と、フェンス補完・消失セクションの注記化を実装。
  - ステージ済み差分（当該コミットのレビュー対象）を全行保持し、ブランチ差分末尾（後方ファイル）を可視化。PRレビュー（優先サブセット無し）は head+tail 保持で後方ファイルを可視化。
  - 切り捨て上限・戦略・最低保証行数を `config.json` で設定化。(`max_diff_lines` /
    `diff_truncation_strategy` / `diff_truncation_context_lines`)。
  - `main.py` / `reply.py`
    の重複切り捨てロジック（3箇所）を共通モジュールへ統一し、フェンス補完漏れも修正。

### Changed

- ランディングページと同梱ドキュメントをソースコードと突き合わせて修正。
  - バージョンバッジを v0.2.1 に更新（`__version__` と整合）。
  - Semgrep カスタムルール数を 7 → 8 に修正（`.semgrep/rules.yml` と整合）。
  - デモの既定モデル表記を sonnet に修正。
  - `static_precheck.py` のサーキットブレーカー説明を実装に合わせて修正。
  - README から削除済みの `VERSION` ファイル参照を除去。
  - LOW エスケープ条件の表記を「LOW/INFO のみが 2 回連続」に統一。

## [0.2.1] - 2026-08-05

### Fixed

- pre-commit の AI レビューで false
  positive が連続しても無限ループしないよう、直近 2 回の返信の類似度による stale 検出（強制 LGTM）を導入。
- 最大ラウンド制限とコメント単位の stale 降格も追加 (Issue #55)。
- opencode エンジンで claude 系モデル既定名の解決漏れを防止し、stale 降格を全エンジンで共通化 (Issue
  #55)。
- PR 差分が空の場合に pre-commit 全体をスキップし、base 側で検証済みの内容を再スキャンしないようにした (Issue
  #49 / #55)。
- CI のパッケージビルド検証で、uv /
  npm キャッシュ（`.cache/`）が sdist に混入して毎回約 15 分かかっていた問題を修正。`.gitignore`
  と hatchling の sdist `exclude` の両方で除外 (Issue #57)。

## [0.2.0] - 2026-08-04

### Added

- エンジン SDK アダプタ層を追加。Claude /
  Antigravity は SDK 直駆動、OpenCode は CLI サブプロセス経由（SDK はサーバ起動型で CI 都度起動が煩雑なため）。
- プロジェクトローカル設定 `.ame-review/` による repo 非依存パス解決。
- 移植先で vendored した `ame_ai_review_system/` 配下を既定でレビュー対象外にする設定を追加 (Issue
  #37)。`review_include_package_dir` で切替可能。
- このリポジトリ自身は `.ame-review/config.json` で `true` に設定し、配下をレビュー対象として運用。

### Changed

- 認証モデルを API キーへ移行。(Claude: `ANTHROPIC_API_KEY`, Antigravity: `GEMINI_API_KEY`,
  OpenCode: `auth.json`)
- 返信判定 (`review_reply.yml` /
  `reply run`) を**インライン返信のみ**トリガーに変更し、トリガーとなったスレッド 1 件だけに LGTM
  / 追加指摘を返信するようにした。投稿直前の保留再チェックも追加し、並走実行による重複 LGTM を防止 (Issue
  #39)。`TRIGGER_COMMENT_ID` 未設定時は従来の全スレッド走査へフォールバック。

### Removed

- PyPI 公開・pip インストール経路を廃止。配布はソースコードコピー方式（`.github/` と
  `ame_ai_review_system/` のコピー）に一本化 (Issue #45)。これに伴い `ame-review init`
  サブコマンド、`.github/workflows/release.yml`、`pyproject.toml` の `[project.scripts]` /
  `[project.optional-dependencies]` / hatchling ビルド設定、 `docs/distribution.md` を削除。
- LLM CLI バイナリ (`claude`/`opencode`/`agy`) のサブプロセス呼び出し。
- 未参照の `ame_ai_review_system/VERSION` ファイル。
