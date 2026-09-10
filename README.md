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
  時にローカルで AI レビューが走り、指摘があればコミットをブロックする（デフォルト ON）。PR レビューと同じプロンプトを使用し、LOW
  / INFO の指摘のみ `precommit_max_reviews`（既定 3）回連続で無限ループ回避の escape
  hatch を用意。前段の静的解析 (ruff / mypy /
  semgrep) が全て pass した場合のみ AI レビューする。`precommit_require_static_checks`
  で ON/OFF 可能（デフォルト ON）。
- **PR レビューの Circuit Breaker**: `/request-review` 実行時に ruff / mypy /
  semgrep の静的解析を先行実行する。1件でもエラーがあれば AI レビューをスキップしてトークン消費を抑制する。`pr_review_require_static_checks`
  で ON/OFF 可能（デフォルト ON）。
- **外部 CI の合否ゲート（Issue #140）**: `pr_review_require_external_ci`（既定
  `false`）で有効化する。 `/request-review` 実行時に HEAD SHA の check
  runs を参照する。外部 CI に失敗があれば AI レビューをスキップして PR へ通知する。読み取りには
  `GITHUB_TOKEN` の `checks: read` を使い、GitHub App 権限には依存しない。
- **Semgrep カスタムルール**: CLAUDE.md §8 のコーディング規約を Semgrep で機械的に検出する。broad
  exception catch 禁止・kill -15 $pids 禁止・echo|python3 -c 禁止 等。ルールは
  `ame_ai_review_system/.semgrep/rules.yml`。
- **プロンプトキャッシュ最適化**: 返信判定プロンプトの固定セクションを先頭に配置する。動的セクション（diff・返信）を末尾に配置し Claude
  API のキャッシュヒット率を最大化。
- **Reasoning Effort の役割別制御**: レビュー時と返信判定時で model /
  thinking を個別設定可能。`review_model`/`reply_model`/
  `review_thinking`/`reply_thinking`。返信判定は haiku/low で推論トークンを削減。
- **Stale-Loop 検出**: レビュアーが同じ指摘を言い換えて繰り返す膠着状態を Jaccard 類似度 (80%閾値) で検出し、強制 LGTM で膠着を打破する。
- **最大ラウンド制限**: 無限レビュー防止のためレビュー回数に上限を設ける。Gate
  1 は LOW/INFO のみ連続時の escape 閾値 `precommit_max_reviews`（既定 3）。Gate
  2 は総レビュー回数のハード上限 `pr_max_reviews`（既定 3）。上限到達時は PR に一度だけ通知する。
- **Diff 圧縮**: git
  diff のメタデータ行・バイナリ差分・連続空行を除去し（RTK アプローチ）、LLM 入力トークンを削減。
- **プロンプト・スリミング（Issue #137）**: Gate
  1 は差分をプロンプトへ埋め込む際、既定では「ステージ済み差分（今回のコミット対象）」のみを含める。ブランチ累積差分（`git diff <base>...HEAD`）はステージ済み差分と重複し reasoning 予算を圧迫して
  `finish=length` 空応答を招くため、`include_branch_diff`（既定
  `false`）で制御する。スタックブランチ等で分岐元の文脈が必要な場合のみ、`config.json` に
  `"include_branch_diff": true` を設定して有効化する。
- **実装エンジンの自動検出**: 実装に使っている AI ツールをプロセスツリーから自動検出する (`precommit_engine="auto"`)。OpenCode で実装していれば、使用したモデルに応じて同じ組合せでレビューする。PR レビューとは独立してエンジン/モデル/思考量を
  `config.json` の `precommit_*` キーや環境変数で上書き可能。
- **ユーザー固有設定オーバーライド**:
  `config.user.json`（Git 管理対象外）で環境依存の設定（エンジン・モデル・思考量など）を上書き可能。`config.json`
  より優先される。
- **グローバル設定**: `~/.config/ame-ai-review-system/config.json` にユーザー単位の共通設定（Gate
  1 の `precommit_*`
  キー）を配置可能。優先順位は 環境変数 > リポジトリ設定 > グローバル設定 > 自動検出。パスは
  `AME_REVIEW_GLOBAL_CONFIG` で変更できる。
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

## ランディングページ（兼 ドキュメントサイト）

プロダクトの設計概要や、コミット前（Gate 1）およびプルリクエスト時（Gate
2）の品質チェックフローをブラウザ上でシミュレーションできる紹介サイトを同梱しています。サイトは
**ドキュメントページ**として構成されています。

左サイドバーのナビゲーションから、使い方・設定・アーキテクチャ・トラブルシューティングを閲覧できます。

公開サイト: <https://ame-team.github.io/AME-AI-Review-System/> （`main` ブランチへの push で GitHub
Pages に自動デプロイされます）

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
    review_command.yml    # `/request-review` コメントでレビューを実行するラッパ（再利用可は review-command.yml）
    review-command.yml    # 再利用可能本体（workflow_call）。`main review` を実行
    review_reply.yml      # インライン返信時に自動返答するラッパ（再利用可は review-reply.yml）
    review-reply.yml      # 再利用可能本体（workflow_call）。`reply run` を実行
    ci.yml                # 本リポジトリのCI設定（pre-commit / pytest / vitest / pyright / wheel 検証）
    release.yml           # `v*` タグ push で wheel/sdist をビルドし GitHub Release に添付
    deploy-landing-page.yml  # main への push でランディングページを GitHub Pages へデプロイ

ame_ai_review_system/    # ★他のリポジトリに丸ごとコピーする資材
  main.py                # CLI エントリポイント（init / review / checkout / setup サブコマンド）
  init_cmd.py            # `ame-ai-reviewer init` 本体（プリセット選択・workflow 生成）
  reply.py               # 返信プロンプト生成・スレッド解析・stale-loop検出
  github_client.py       # GitHub REST/GraphQL API 共通クライアント（Resolve 等の GraphQL 操作を含む）
  engine.py              # LLM エンジンアダプタ（claude/opencode/antigravity を切替・role別設定）
  payload.py             # モデル出力 -> GitHub API ペイロード変換
  review_config.py       # 設定読み込み・コマンド判定ヘルパ
  static_precheck.py     # PR レビュー前段の静的解析 pre-check（Circuit Breaker）
  diff_utils.py          # diff 圧縮ユーティリティ（RTK アプローチ）
  diff_base.py           # pre-commit ローカルレビュー用の diff 比較元（upstream/fork-point）自動解決
  diff_truncate.py       # 戦略的 diff 切り捨て（priority / front / head_tail）
  pr_streak.py           # PR レビューの streak 管理（2回連続LOWで終了）
  stale_detect.py        # stale-loop 検出（Jaccard 類似度）・LGTM 判定の共通実装
  skip_guard.py          # `SKIP=ai-precommit-review` バイパスの強制ブロック（ネイティブ Git フック連携）
  paths.py               # 設定・プロンプト・engines-ts 等のパス解決
  precommit_review.py    # pre-commit AI レビュー本体
  precommit_engine.py    # pre-commit レビューのエンジン解決・自動検出
  precommit_state.py     # pre-commit レビューの状態管理モジュール
  post_commit_reset.py   # post-commit で streak カウンタをリセット
  mermaid_check.py       # Mermaid 記法バリデータ
  setup.py               # 開発環境セットアップ補助
  config.json            # 動作設定（precommit/PR 自動レビューの ON/OFF、エンジン/モデル/思考量 等）
  review_prompt.txt      # レビュアーへのプロンプト（レビュー観点・静的解析移管後の軽量版）
  .semgrep/rules.yml     # Semgrep カスタムルール（CLAUDE.md §8 コーディング規約の機械的強制）8ルール

  engines/               # LLM エンジン用サイドカー（opencode/claude の TS アダプタ）
  templates/             # `init` が参照するテンプレート（preset / workflow ラッパ / ame-review 設定）
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
  install-hooks.sh             # ネイティブ Git フック有効化（core.hooksPath=githooks、SKIP バイパス対策）
  check_wheel_assets.sh        # wheel の同梱資産（engines-ts / templates / docs）検証
```

## クイックスタート

本システムは GitHub
Release のタグ付き wheel を配布している（PyPI 非公開）。他プロジェクトへの導入は非常にシンプルです。

1. **コアの導入**（いずれかを選択）:

   **方式 A: wheel インストール（推奨）**

   ```bash
   pip install https://github.com/AME-Team/AME-AI-Review-System/releases/download/v0.1.0/ame_ai_review_system-0.1.0-py3-none-any.whl
   ```

   `uv` を使う場合（pipx と同等の CLI ツール管理）も利用できる。

   ```bash
   # 導入
   uv tool install "ame-ai-review-system @ https://github.com/AME-Team/AME-AI-Review-System/releases/download/v0.1.0/ame_ai_review_system-0.1.0-py3-none-any.whl"

   # アップグレード
   uv tool upgrade "ame-ai-review-system" --from "https://github.com/AME-Team/AME-AI-Review-System/releases/download/v0.1.0/ame_ai_review_system-0.1.0-py3-none-any.whl"
   ```

   > [!NOTE] pipx と uv はどちらも `~/.local/bin`
   > に同一バイナリ（`ame-ai-reviewer`）を配置するため共存できません。切り替え時は一方を uninstall してください。

   URL の `v0.1.0` は例。[Releases](https://github.com/AME-Team/AME-AI-Review-System/releases)
   ページの最新バージョンに置き換えること。

   `ame-ai-reviewer init` で設定・ワークフローを生成する。TS エンジン (opencode /
   claude-ts) を使う場合は `--with-engines`
   を付ける。npm 依存のインストールも自動化される (`.ame-review/engines-ts/` に展開)。

   ```bash
   ame-ai-reviewer init --preset python --ref v0.1.0 --with-engines
   ```

   - `--preset`: pre-commit 静的解析セット (`auto` / `full` / `python` / `text` / `ts` /
     `minimal`)。 `auto` (既定) は `package.json` + `.ts`/`.tsx` ソースの有無で `ts` か `full`
     を自動選択する (Issue #69)。`ts` プリセットの eslint / tsc / prettier / stylelint は
     `./node_modules/.bin` を直接起動するため、事前に `npm install`
     (または pnpm/yarn) が必要 (未実施時は「No such file or directory」で失敗する)
   - `--ref`: reusable workflow の参照 (リリースタグ or ブランチ)
   - `--version`: Gate 1 (pre-commit
     AI フック) が参照する wheel のバージョン。省略時はインストール済みパッケージの
     `__version__`。release の wheel を `#sha256=` で内容固定して参照する (Issue #84)。
   - `--python`: オフライン環境向け。指定すると Gate 1 フックを `language: system`
     で生成し、Python インタープリタパスを埋め込む。省略時は wheel 方式 (`language: python`) で生成し、絶対パスを埋め込まない。生成物は共有・コミットしても他環境/CI で動作する (Issue
     #79)。 `AME_INIT_PYTHON` 環境変数でも system 方式へ切り替わる (Issue #66)。

   > [!NOTE] **生成物は移植可能**: 既定の `language: python`
   > 方式では pre-commit が各環境で venv を自動作成し wheel を導入するため、絶対パスが埋め込まれません。
   > `--python`
   > で生成した場合は埋め込んだ絶対パスが init 実行環境に依存するため、そのまま別マシン/CI では動きません。共有が必要な場合は wheel 方式で生成するか、各環境で
   > `ame-ai-reviewer init` を実行してください (Issue #79)。

   生成物は以下のとおり。

   - `.ame-review/config.json`
   - `.ame-review/review_prompt.txt`
   - `.pre-commit-config.yaml`
   - `.github/workflows/review_command.yml`
   - `.github/workflows/review_reply.yml`

   CI は reusable workflow を呼ぶ薄いラッパ。更新は `--ref` の差し替えのみ。

   > [!IMPORTANT] **Gate 2 の静的解析は `/request-review` 実行時のみ**。`init` が生成するのは
   > `review_command.yml` / `review_reply.yml` のラッパのみで、 **push /
   > pull_request 時に走る静的解析 CI は含まれない**。PR レビュー（Gate 2）の Circuit Breaker（ruff
   > / mypy / semgrep の先行静的解析）は、PR コメントで `/request-review`
   > を入力したタイミングでのみ実行される。
   >
   > ブランチへの push 時にも静的解析を回したい場合は、wheel に同梱の
   > `ame_ai_review_system/templates/workflow/ci.yml` （`init --preset` 相当の静的解析ジョブ）を
   > `.github/workflows/ci.yml` として配置すること。AI レビューフックは `/request-review`
   > 側で実行されるため、このテンプレートではスキップする（[セットアップガイド](ame_ai_review_system/docs/setup.md)
   > の「配布先向け静的解析 CI」を参照）。

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
     curl -fsSL https://raw.githubusercontent.com/AME-Team/AME-AI-Review-System/v0.1.0/.claude/skills/review-round/SKILL.md \
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

4. **プロンプトの調整**: `.ame-review/review_prompt.txt`（`init` 生成物）を編集する。
   `paths.prompt_path()`
   はこのパスを優先する。init 生成時はパッケージ既定と一致するが、編集後は生成物がプロジェクトのカスタマイズ単位となる (Issue
   #111)。
5. **レビュー依頼**: PR を作成したら、PR コメントで `/request-review` を入力してレビューを依頼する。

> [!NOTE] **エンジン別の SDK**: 既定の `opencode` エンジンはワークフローが TypeScript
> SDK を自動導入します。`claude` / `antigravity` エンジンを使う場合は Python SDK（`claude-agent-sdk`
> / `google-antigravity`）が必要です。エンジン別の認証・モデル設定などの詳細は
> [セットアップガイド](ame_ai_review_system/docs/setup.md)を参照してください。
>
> [!NOTE] **pre-commit 時の AI レビューもデフォルトで有効** です。`git commit`
> 時にローカルで AI レビューが走り、指摘があればコミットをブロックします。PR レビューとは独立して
> `ame_ai_review_system/config.json` の `precommit_review_enabled` で ON/OFF できます。生成される
> `.pre-commit-config.yaml` は `default_install_hook_types: [pre-commit, post-commit]`
> を指定しているため、 `pre-commit install`
> だけで post-commit フック（streak リセット）も導入されます (Issue #82)。既存クローンで
> `pre-commit install` 済みの場合は以下で再実行してください:
>
> ```bash
> pre-commit install -t pre-commit -t post-commit
> ```
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
