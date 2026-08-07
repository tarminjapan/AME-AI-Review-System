# AME-AI-Review-System

![AME AI Review System](landing-page/src/assets/header-image.svg)

> **「静的解析（Linter/型検査）」と「AIレビュー」を融合し、ローカル（pre-commit）と CI（PR）の二重ゲートでコード品質を担保する、簡単移植可能な開発フィロソフィー（IPアセット）パッケージ。**

## 概要

本システムは、ローカル（pre-commit）と CI（PR）の両方で「静的解析と AI レビュー」を組み合わせる仕組みです。二重の品質ゲートにより、高品質なコード管理（IPアセット）を簡単に導入します。

機械的な「Linterや型検査」を前段で実行し、無駄な LLM コストを削減する Circuit
Breaker を備えています。ローカルで早期に検知する Shift-Left を徹底し、高品質なコードのみが PR に到達するよう強制します。

### 二重の品質ゲート構成

```text
[ ローカル開発 (Git Commit) ]
  └── Gate 1: pre-commit ゲート (静的解析 + AI レビュー)
        └── staged ファイルに対し ruff/mypy/semgrep 等を実行。パスした場合のみローカル AI レビューを実行。

[ CI/CD 環境 (Pull Request) ]
  └── Gate 2: PR ゲート (Circuit Breaker 静的解析 + AI レビュー)
        └── コメント `/request-review` 時に ruff/mypy/semgrep 等を実行。エラーが 0 件の場合のみ AI レビューを実行。
```

### 静的解析プリセット一覧

本システムでは、機械的に検出可能な問題は LLM 呼び出し前に静的解析により高い精度でキャッチする思想を徹底しています。以下の約25個のツール群が既定の品質チェックとして動作します。

| カテゴリ               | 採用ツール・検査内容                                                              | 主な設定ファイル                                            |
| ---------------------- | --------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| **Python**             | ruff (lint, ALL+preview), ruff-format, mypy (strict), pyright                     | `pyproject.toml`                                            |
| **セキュリティ**       | semgrep-custom（自作8ルール）, gitleaks, detect-private-key                       | `ame_ai_review_system/.semgrep/rules.yml`, `.gitleaks.toml` |
| **フロントエンド**     | eslint (`--max-warnings=0`), tsc `--noEmit`, stylelint                            | `eslint.config.mjs`, `tsconfig.json`                        |
| **ドキュメント/文章**  | markdownlint-cli2, textlint, codespell, mermaid-check（自作）                     | `.markdownlint-cli2.jsonc`, `.textlintrc`                   |
| **設定/データ**        | yamllint (strict), check-yaml / check-toml / check-json, sqlfluff                 | `.yamllint.yaml`, `.sqlfluff`                               |
| **シェル/CI**          | shellcheck, actionlint                                                            | `.shellcheckrc`, `.actionlint.yaml`                         |
| **Git衛生**            | commitlint, check-merge-conflict, check-case-conflict, check-added-large-files 等 | `.commitlintrc.json`, pre-commit-hooks                      |
| **フォーマット**       | prettier-root                                                                     | `.prettierrc`                                               |
| **自作リポジトリ規約** | prohibit-suppression-comments, repo-hygiene                                       | `scripts/check_suppression_comments.py`                     |
| **テスト**             | pytest, vitest（pre-push / pre-merge-commit 連携）                                | `pyproject.toml`, `vitest.config.ts`                        |

本リポジトリは、別のプロジェクトへ簡単に移植可能です。 `pip install`（GitHub
Release の wheel）または `.github/` と `ame_ai_review_system/` のコピペで導入できます。

## 特徴

- **ベースブランチとの全累積差分レビュー**: 従来のコミット単位の差分チェックでは複数コミットを含むPRの全容把握が困難であった。本システムは
  `origin/<base>...HEAD`（既定は
  `main`）の全累積差分を評価対象とし、PR全体の整合性を正確に追跡・評価する。
- **ブランチフロー**: 作業ブランチ（feature / bug / chore 等） → `main`。AI Agent はデフォルトで
  `main` をベースに PR を作成する。
- **厳格なデフォルト静的解析**: tsc / eslint (--max-warnings=0) / mypy / ruff /
  semgrep 等の約25ツールを標準装備。機械的な問題は前段にて高い精度で捕捉する構造である。
- **Gate 1（pre-commit）& Gate 2（PR）の二重品質ゲート**: ローカルコミット時（Gate 1）とCI/CD
  PR時（Gate 2）の二段階で静的解析とAIレビューを実施する。欠陥の早期検出（Shift-Left）を実現する。
- **マルチCodingエージェント対応 & 広範なコンテキスト検証**: Claude Code / OpenCode / Antigravity
  CLI 等を指定可能。Codingエージェントが差分外領域も自発的に探索し「コード修正に伴うドキュメント更新の有無」なども高度に検証する。
- **コマンド駆動のレビュー**: PR コメントで `/request-review` を入力したタイミングでレビューが走る。
- **pre-commit 時の AI レビュー**: `git commit`
  時にローカルで AI レビューが走り、指摘があればコミットをブロックする（デフォルト ON）。PR レビューと同じプロンプトを使用し、LOW レベル指摘のみ 2 回連続で無限ループ回避の escape
  hatch を用意。前段の静的解析 (ruff / mypy /
  semgrep) が全て pass した場合のみ AI レビューする。`precommit_require_static_checks`
  で ON/OFF 可能（デフォルト ON）。
- **PR レビューの Circuit Breaker**: `/request-review` 実行時に ruff / mypy /
  semgrep の静的解析を先行実行する。1件でもエラーがあれば AI レビューをスキップしてトークン消費を抑制する。`pr_review_require_static_checks`
  で ON/OFF 可能（デフォルト ON）。
- **Semgrep カスタムルール**: CLAUDE.md §8 のコーディング規約を Semgrep で機械的に検出する。broad
  exception catch 禁止・kill -15 $pids 禁止・echo|python3 -c 禁止 等。ルールは
  `ame_ai_review_system/.semgrep/rules.yml`。
- **プロンプトキャッシュ最適化**: 返信判定プロンプトの固定セクションを先頭に配置する。動的セクション（diff・返信）を末尾に配置し Claude
  API のキャッシュヒット率を最大化。
- **Reasoning Effort の役割別制御**: レビュー時と返信判定時で model /
  thinking を個別設定可能。`review_model`/`reply_model`/
  `review_thinking`/`reply_thinking`。返信判定は haiku/low で推論トークンを削減。
- **Stale-Loop 検出**: レビュアーが同じ指摘を言い換えて繰り返す膠着状態を Jaccard 類似度 (80%閾値) で検出し、強制 LGTM で膠着を打破する。
- **Diff 圧縮**: git
  diff のメタデータ行・バイナリ差分・連続空行を除去し（RTK アプローチ）、LLM 入力トークンを削減。
- **実装エンジンの自動検出**: 実装に使っている AI ツールをプロセスツリーから自動検出する (`precommit_engine="auto"`)。OpenCode で実装していれば、使用したモデルに応じて同じ組合せでレビューする。PR レビューとは独立してエンジン/モデル/思考量を
  `config.json` の `precommit_*` キーや環境変数で上書き可能。
- **ユーザー固有設定オーバーライド**:
  `config.user.json`（Git 管理対象外）で環境依存の設定（エンジン・モデル・思考量など）を上書き可能。`config.json`
  より優先される。
- **簡単移植**: 2 つの導入方式を提供。
  - **wheel インストール（推奨）**: GitHub Release の wheel を `pip install`
    し、`ame-ai-reviewer init` で設定・ワークフローを生成する。CI は reusable
    workflow を呼ぶ薄いラッパで、更新は参照タグの差し替えのみ。
  - **ディレクトリコピー**: `.github/` と `ame_ai_review_system/`
    を他リポジトリにコピーする方式（オフライン環境や細かなカスタマイズ時に）。
- **対話型の修正サイクル**: 開発者が `@<レビュアー名>`
  で返信すると、AI が最新コードを再評価してスレッドに返答。
- **重大度ラベル**: 指摘を `CRITICAL` / `HIGH` / `MIDDLE` / `LOW` の 4 段階で分類。
- **複数レビュアー対応**: ジョブの追加だけで、役割の異なる複数のレビュアーを追加可能。
- **マルチエンジン**: `config.json` / 環境変数で Claude Code・OpenCode・Antigravity
  CLIを切り替え可能。エンジン・モデル・思考量(high/medium/low)を設定ファイルで指定できる。

## ランディングページ

プロダクトの設計概要や、コミット前（Gate 1）およびプルリクエスト時（Gate
2）の品質チェックフローをブラウザ上でシミュレーションできるインタラクティブな紹介サイトを同梱しています。

公開サイト: <https://tarminjapan.github.io/AME-AI-Review-System/> （`main`
ブランチへの push で GitHub Pages に自動デプロイされます）

### 起動・ビルドコマンド

```bash
# 依存パッケージのインストール
npm install

# 開発サーバーの起動 (http://localhost:5173)
npm run dev --workspace=landing-page

# 本番用ビルドの実行
npm run build --workspace=landing-page

# ビルド成果物のローカルプレビュー
npm run preview --workspace=landing-page
```

## ディレクトリ構成

```text
.github/
  workflows/
    review_command.yml    # `/request-review` コメントでレビューを実行するワークフロー
    review_reply.yml      # コメント返信時に自動返答を実行するワークフロー
    ci.yml                # 本リポジトリのCI設定（pre-commit / pytest / pyright）

ame_ai_review_system/    # ★他のリポジトリに丸ごとコピーする資材
  main.py                # CLI エントリポイント（review / checkout / setup サブコマンド）
  reply.py               # 返信プロンプト生成・スレッド解析・stale-loop検出
  github_client.py       # GitHub REST/GraphQL API 共通クライアント（Resolve 等の GraphQL 操作を含む）
  engine.py              # LLM エンジンアダプタ（claude/opencode/antigravity を切替・role別設定）
  payload.py             # モデル出力 -> GitHub API ペイロード変換
  review_config.py       # 設定読み込み・コマンド判定ヘルパ
  static_precheck.py     # PR レビュー前段の静的解析 pre-check（Circuit Breaker）
  diff_utils.py          # diff 圧縮ユーティリティ（RTK アプローチ）
  pr_streak.py           # PR レビューの streak 管理（2回連続LOWで終了）
  precommit_review.py    # pre-commit AI レビュー本体
  precommit_engine.py    # pre-commit レビューのエンジン解決・自動検出
  precommit_state.py     # pre-commit レビューの状態管理モジュール
  post_commit_reset.py   # post-commit で streak カウンタをリセット
  mermaid_check.py       # Mermaid 記法バリデータ
  setup.py               # 開発環境セットアップ補助
  config.json            # 動作設定（push/precommit 自動レビューの ON/OFF、エンジン/モデル/思考量 等）
  review_prompt.txt      # レビュアーへのプロンプト（レビュー観点・静的解析移管後の軽量版）
  .semgrep/rules.yml     # Semgrep カスタムルール（CLAUDE.md §8 コーディング規約の機械的強制）

  docs/                   # 同梱ドキュメント
    setup.md              # 移植・セットアップ手順
    architecture.md       # システムアーキテクチャ・処理の流れ
    customization.md      # プロンプトやレビュアーのカスタマイズ
    troubleshooting.md    # よくあるエラーと対処法
    instructions.md       # AIレビューフロー指示書（開発者・AIエージェント向け）

scripts/
  linux/
    pr_review_reply.sh         # レビュー返信ワークフロー互換のレガシーパス（互換ラッパ）
  precommit_hygiene.py         # pre-commit 関連の補助スクリプト
  check_suppression_comments.py  # 抑制コメント検証スクリプト
```

## クイックスタート

本システムは GitHub
Release のタグ付き wheel を配布している（PyPI 非公開）。他プロジェクトへの導入は非常にシンプルです。

1. **コアの導入**（いずれかを選択）:

   **方式 A: wheel インストール（推奨）**

   ```bash
   pip install https://github.com/tarminjapan/AME-AI-Review-System/releases/download/v0.1.0/ame_ai_review_system-0.1.0-py3-none-any.whl
   ```

   URL の `v0.1.0` は例。[Releases](https://github.com/tarminjapan/AME-AI-Review-System/releases)
   ページの最新バージョンに置き換えること。

   `ame-ai-reviewer init` で設定・ワークフローを生成する。TS エンジン (opencode /
   claude-ts) を使う場合は `--with-engines`
   を付ける。npm 依存のインストールも自動化される (`.ame-review/engines-ts/` に展開)。

   ```bash
   ame-ai-reviewer init --preset python --ref v0.1.0 --with-engines
   ```

   - `--preset`: pre-commit 静的解析セット (`full` / `python` / `text` / `minimal`)
   - `--ref`: reusable workflow の参照 (リリースタグ or ブランチ)
   - `--python`: Gate 1 (pre-commit AI フック) が使う Python インタープリタパス。
     省略時は `AME_INIT_PYTHON` 環境変数、次に `ame-ai-reviewer` 自身を実行中の
     インタープリタ (`sys.executable`) となる。Ubuntu 24 等 PEP 668
     (externally-managed) 環境では、venv / `uv tool` / `pipx` の Python を明示するか
     それらの中から `ame-ai-reviewer` を実行することで Gate 1 が動作する (Issue #66)。

   > [!NOTE] **生成物は機械固有**: `--python` で埋め込んだ絶対パスは init 実行環境に
   > 依存するため、生成された `.pre-commit-config.yaml` はそのまま別マシン/CI では
   > 動きません。各環境で `ame-ai-reviewer init` を実行するか、共有が必要な場合は
   > `AME_INIT_PYTHON` で環境ごとに解決してください (Issue #66)。

   生成物は以下のとおり。

   - `.ame-review/config.json`
   - `.ame-review/review_prompt.txt`
   - `.pre-commit-config.yaml`
   - `.github/workflows/review_command.yml`
   - `.github/workflows/review_reply.yml`

   CI は reusable workflow を呼ぶ薄いラッパ。更新は `--ref` の差し替えのみ。

   LLM エンジン SDK は個別に導入する（オプション）。

   ```bash
   pip install claude-agent-sdk       # Claude Python SDK
   pip install google-antigravity     # Antigravity (Gemini)
   ```

   **方式 B: ディレクトリコピー**（オフライン環境・細かなカスタマイズ向け）

   ```bash
   cp -r .github/ /path/to/your-repo/
   cp -r ame_ai_review_system/ /path/to/your-repo/
   ```

   > [!NOTE] **CI ワークフロー連携**: 方式 A は `ame-ai-reviewer init` が reusable
   > workflow の薄いラッパを生成する。方式 B は `.github/` をコピーする（従来方式）。

2. **AI エージェント用スキル（review-round）の導入**（推奨）: `.claude/skills/review-round/SKILL.md`
   にスキルを配置する。これにより AI エージェントが Dual-Gate レビューラウンド（Gate 1 → Gate
   2）を自律的に完遂できる。

   - **方式 A**（wheel インストール時）:

     ```bash
     mkdir -p .claude/skills/review-round
     curl -fsSL https://raw.githubusercontent.com/tarminjapan/AME-AI-Review-System/v0.1.0/.claude/skills/review-round/SKILL.md \
       -o .claude/skills/review-round/SKILL.md
     ```

     （`v0.1.0` は手順 1 の `--ref` と同じリリースタグに揃える）

   - **方式 B**（ディレクトリコピー時）: `.claude/skills/review-round/` もあわせてコピーする。

     ```bash
     mkdir -p <your-repo>/.claude/skills
     cp -r .claude/skills/review-round <your-repo>/.claude/skills/review-round
     ```

3. **GitHub App の登録と Secret 設定**: レビュー用の GitHub
   App を作成し、対象リポジトリにインストールする。App の Credentials として以下を Secrets に登録する。
   - `AME_AI_REVIEWER_APP_ID` : GitHub App の App ID（数値）
   - `AME_AI_REVIEWER_APP_PRIVATE_KEY` : 生成した Private Key（`.pem` 内容全体）

   必要な App 権限: `Contents: Read` / `Pull requests: Read & Write` /
   `Issues: Read & Write`。CI ワークフローは `actions/create-github-app-token@v2`
   で都度インストールトークンを取得する。

4. **プロンプトの調整**: `ame_ai_review_system/review_prompt.txt`
   をプロジェクトの規約や観点に合わせてカスタマイズする。
5. **レビュー依頼**: PR を作成したら、PR コメントで `/request-review` を入力してレビューを依頼する。

> [!NOTE] **エンジン別の SDK**: 既定の `opencode` エンジンはワークフローが TypeScript
> SDK を自動導入します。`claude` / `antigravity` エンジンを使う場合は Python SDK（`claude-agent-sdk`
> / `google-antigravity`）が必要です。エンジン別の認証・モデル設定などの詳細は
> [セットアップガイド](ame_ai_review_system/docs/setup.md)を参照してください。
>
> [!NOTE] **pre-commit 時の AI レビューもデフォルトで有効** です。`git commit`
> 時にローカルで AI レビューが走り、指摘があればコミットをブロックします。PR レビューとは独立して
> `ame_ai_review_system/config.json` の `precommit_review_enabled` で ON/OFF できます。利用には
> `pre-commit install --install-hooks -t pre-commit -t commit-msg -t pre-push -t post-commit`
> で post-commit フックもインストールする必要があります。
>
> [!IMPORTANT] **AI レビューの SKIP バイパスを強制ブロックする場合はネイティブ Git フックを有効化**
> してください（Issue #26）。`bash scripts/install-hooks.sh` を実行すると `core.hooksPath=githooks`
> が設定され、`SKIP=ai-precommit-review` を AI Agent が勝手に使えなくなります（`githooks/pre-commit`
> が pre-commit フレームワークの SKIP が届かないレイヤで検査します）。

ユーザー固有の設定は
`ame_ai_review_system/config.user.json`（Git 管理対象外）で上書き可能です。例えば Gate
1 のエンジンだけ変更したい場合は `{"precommit_engine": "claude", "precommit_model": "sonnet"}`
のように記述します。詳細は[カスタマイズガイド](ame_ai_review_system/docs/customization.md)を参照。

より詳細な手順は、[セットアップガイド](ame_ai_review_system/docs/setup.md) を参照してください。

## 関連ドキュメント

- [セットアップガイド](ame_ai_review_system/docs/setup.md) — 移植手順と初期設定の詳細
- [アーキテクチャ解説](ame_ai_review_system/docs/architecture.md) — システムの処理シーケンスと仕組み
- [カスタマイズガイド](ame_ai_review_system/docs/customization.md)
  — プロンプトの修正、複数レビュアーの追加
- [自動レビュー対応フロー指示書](ame_ai_review_system/docs/instructions.md)
  — 人間・AI がレビューに対応するための手順とルール
- [トラブルシューティング](ame_ai_review_system/docs/troubleshooting.md)
  — 動作しない、無限ループが発生したなどの対応
- [開発フロー (CLAUDE.md)](CLAUDE.md) — 本リポジトリ開発者向けの運用ルール

## ライセンス

本プロジェクトは [MIT License](LICENSE) の下で公開されています。
