# セットアップガイド

本ガイドは、静的解析とAIレビューを組み合わせた二重ゲートのレビューシステムを別のリポジトリへ導入するための手順です。

## 1. 前提条件

| 項目         | 要件                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **GitHub**   | 対象リポジトリが GitHub 上に存在し、Actions が有効化されていること。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| **ランナー** | GitHub-hosted `ubuntu-latest`（デフォルト）。ツールチェーン (Python 3.12 / Node 22 / uv / shellcheck / actionlint / gitleaks / claude-code / opencode-ai) は `.github/workflows/ci.yml` の `steps:` で都度セットアップされるため、ランナー側の事前準備は不要。`claude-code` / `opencode-ai` の役割は下記「LLM SDK」行を参照。                                                                                                                                                                                                                                                                                     |
| **LLM SDK**  | 使用するエンジンの SDK（既定: Claude Agent SDK）がランナー上で認証済みであること（認証情報は GitHub Secrets 経由で渡す）。`opencode` は TypeScript SDK（`@opencode-ai/sdk`）サイドカー経由で動作し、サーバ起動に `opencode` CLI（`opencode serve`）が必要。TypeScript SDK を使うエンジン（`claude` の `sdk_lang=typescript` / `opencode`）は `engines/ts/` 配下の npm 依存もインストールすること。`antigravity` は `google-antigravity` Python SDK を使用（[アーキテクチャ](architecture.md)参照）。エンジン本体は SDK 経由だが、SDK の認証基盤・OpenCode サーバ起動のために各 CLI がランナーに必要な場合がある。 |
| **Python**   | Python 3.10 以上（外部依存ライブラリは不要、標準ライブラリのみで動作）。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |

> [!NOTE] **CI/セキュリティツールのバージョン管理** shellcheck / actionlint /
> gitleaks は既知脆弱性回避のため GitHub Releases から latest を取得する。GitHub-hosted ランナーの
> `GITHUB_TOKEN`
> によりレート制限が緩和されるため、フォールバック出現頻度は低い。FALLBACK バージョンは `ci.yml`
> にハードコードされているため、四半期を目安に見直すことを推奨する。

### 1-1. 開発端末（ローカル環境）の準備

> [!NOTE] この節は **本リポジトリ（AME-AI-Review-System）自体の開発・コントリビュート**
> を行う人向けです。別のリポジトリへ導入する（ディレクトリコピー）だけの場合は本節を飛ばして
> [2. 移植手順](#2-移植手順) へ進んでください。

リポジトリ自体の Linter や型チェック（pre-commit）を動作させるための前提ツールと依存関係のセットアップ手順です。

#### エンジン認証トークンの生成

各 LLM エンジンの長期トークンを生成します。使用するエンジンのみ実行してください。

**Claude（Anthropic）の場合:**

```bash
claude setup-token
```

> 生成されたトークンは `~/.claude/.credentials.json` に保存されます。

**OpenCode の場合:**

```bash
opencode providers login
```

> プロバイダーを選択し、API キーを入力します。認証情報は `~/.local/share/opencode/auth.json`
> に保存されます。

> [!NOTE] **ローカル Gate 1 の OpenCode サーバー (Issue #113)**: pre-commit
> AI レビュー (opencode エンジン) は OpenCode サーバーへ接続する。未起動の場合はアダプタが
> `opencode serve --port 4096` を自動起動する。手動で起動する場合は以下を実行すること。
>
> ```bash
> opencode serve --port 4096
> ```
>
> サーバーが無応答 (ヘッダータイムアウト等) になった場合は再起動すること。

**OpenCode + OpenRouter の場合（API Key 認証）:**

OpenCode は OpenRouter を公式プロバイダーとしてサポートしている。OpenRouter 経由で外部モデル（例:
`Tencent/Hy3`）を使う場合、以下の手順で API Key を登録する。

1. [OpenRouter Dashboard](https://openrouter.ai/settings/keys) で "Create API Key" をクリックし、API
   Key をコピーする。
2. OpenCode の認証コマンドを実行し、**OpenRouter** を選択して API Key を貼り付ける。TUI の
   `/connect` または CLI の `opencode providers login` のいずれでも登録可能であり、どちらも
   `~/.local/share/opencode/auth.json` に保存される。

   ```bash
   opencode providers login   # CLI で認証（プロンプトに従って OpenRouter を選択）
   ```

   > OpenRouter 経由のモデル名は `openrouter/<org>/<model>` 形式で指定する。例:
   > `openrouter/tencent/hy3:free`。`/models` コマンドで利用可能なモデルを確認できる。

3. **ローカル（Gate 1）で使う場合**: `ame_ai_review_system/config.user.json`
   を作成し、モデル名を指定する。

   ```json
   {
     "precommit_engine": "opencode",
     "precommit_model": "openrouter/tencent/hy3:free",
     "precommit_thinking": "medium"
   }
   ```

4. **CI（Gate 2）で使う場合**: 認証ファイルを Base64 化して GitHub
   Secret に登録する。Variables にエンジン・モデルを設定する（[カスタマイズガイド §6](customization.md#6-ci-gate-2-のカスタマイズ)参照）。

**Antigravity（Google Gemini）の場合:**

```bash
agy --login
```

> ブラウザで Google アカウントの OAuth 認証が開始されます。認証後、refresh トークンが
> `~/.gemini/antigravity-cli/antigravity-oauth-token` に自動保存されます。

#### 前提ツールのインストール

```bash
# 前提ツールのインストール
# 1. uv のインストール
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# 2. shellcheck / gitleaks のインストール
sudo apt update && sudo apt install -y shellcheck gitleaks

# 3. actionlint のインストール (バイナリダウンロードとチェックサム検証)
ACTIONLINT_VER=$(curl -s https://api.github.com/repos/rhysd/actionlint/releases/latest | grep -oP '"tag_name": "v\K[^"]+')
ACTIONLINT_ARCH=$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')
ACTIONLINT_FILE="actionlint_${ACTIONLINT_VER}_linux_${ACTIONLINT_ARCH}.tar.gz"
curl -sSLO "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VER}/${ACTIONLINT_FILE}"
curl -sSL "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VER}/actionlint_${ACTIONLINT_VER}_checksums.txt" | sha256sum --check --ignore-missing
tar -xz -f "${ACTIONLINT_FILE}" -C ~/.local/bin actionlint
rm -f "${ACTIONLINT_FILE}"

# 仮想環境の作成と有効化
uv venv .venv --python 3.12
source .venv/bin/activate

# Python 依存ライブラリのインストール
uv pip install -r requirements-dev.txt

# Node.js 依存パッケージのインストール
npm ci

# Git フックの登録
pre-commit install --install-hooks -t pre-commit -t commit-msg -t pre-push -t post-commit

# (推奨) AI レビューの SKIP バイパスを強制ブロックするネイティブ Git フックを有効化 (Issue #26)
bash scripts/install-hooks.sh
```

> [!IMPORTANT] **pre-commit AI レビューを使う場合は `-t post-commit` が必須**
> です。post-commit フックが無いと、コミット成功時の streak リセットが走りません。
>
> [!IMPORTANT] **`scripts/install-hooks.sh` を実行すると `core.hooksPath=githooks`
> が設定されます**。これにより `SKIP=ai-precommit-review` による Gate1 AI レビューのバイパスを、AI
> Agent が勝手に行えないよう強制ブロックします（ネイティブフックが pre-commit フレームワークの SKIP 制御の及ばないレイヤで検査）。バックグラウンドは
> [Issue #26](https://github.com/AME-Team/AME-AI-Review-System/issues/26) を参照。

---

## 2. 移植手順

別のリポジトリに本システムを導入する手順は以下の通りです。

### Step 1: コアの導入（方式 A / B から選択）

#### 方式 A: wheel インストール（推奨）

最新 Release の wheel を `pip install` する。

```bash
pip install https://github.com/AME-Team/AME-AI-Review-System/releases/download/v0.1.0/ame_ai_review_system-0.1.0-py3-none-any.whl
```

`uv` を使う場合（pipx と同等の CLI ツール管理）も利用できます。

```bash
uv tool install "ame-ai-review-system @ https://github.com/AME-Team/AME-AI-Review-System/releases/download/v0.1.0/ame_ai_review_system-0.1.0-py3-none-any.whl"
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
  `minimal`)。`auto` (既定) は `package.json` と `.ts`/`.tsx` ソースの有無から `ts` か `full`
  を自動選択する (Issue #69)。`ts` プリセットの eslint / tsc / prettier / stylelint は
  `./node_modules/.bin` を直接起動するため、事前に `npm install` が必要
- `--ref`: reusable workflow の参照 (リリースタグ or ブランチ)。`--no-workflow` 指定時以外は必須
- `--version`: Gate 1 (pre-commit
  AI フック) が参照する wheel のバージョン。省略時はインストール済みパッケージの
  `__version__`。release の wheel を `#sha256=` で内容固定して参照する (Issue #84)。
- `--engine`: Gate 1 (pre-commit AI フック) の既定エンジン (`auto` / `claude` / `opencode` /
  `antigravity`)。
- `claude` / `antigravity` 指定時は SDK を `additional_dependencies` へ追加する。
- SDK 名: `claude-agent-sdk` / `google-antigravity` (Issue #114)。
- これにより pre-commit の隔離 venv で該当エンジンを起動できる。
- `auto` (既定) は実行時にプロセスツリーから自動検出する。SDK は追加しない。
- `--python`: オフライン環境向け。指定すると Gate 1 フックを `language: system`
  で生成し、指定した Python インタープリタパスを埋め込む。省略時は wheel 方式 (`language: python`) で生成され、絶対パスを埋め込まないため生成物を共有・コミットしても他環境/CI で動作する (Issue
  #79)。`AME_INIT_PYTHON` 環境変数でも同様に system 方式へ切り替わる (Issue #66)。
- `--no-workflow`: CI ラッパワークフロー (`review_command.yml` /
  `review_reply.yml`) の生成をスキップする
- `--with-engines`:
  TS エンジンサイドカー (`.ame-review/engines-ts/`) を展開し npm 依存をインストールする
- `--force`: 既存ファイルを上書きする。既定は「ファイルが存在すればスキップ」

生成物は以下のとおり。

- `.ame-review/config.json`
- `.ame-review/review_prompt.txt`
- `.pre-commit-config.yaml`
- `.github/workflows/review_command.yml`
- `.github/workflows/review_reply.yml`

CI は reusable workflow を呼ぶ薄いラッパ。更新は `--ref` の差し替えのみ。

> [!IMPORTANT] **Gate 2 の静的解析は `/request-review` 実行時のみ**。`init` が生成するのは
> `review_command.yml` / `review_reply.yml` のラッパのみで、 **push /
> pull_request 時に走る静的解析 CI は含まれません**。PR レビュー（Gate 2）の Circuit Breaker（ruff /
> mypy / semgrep の先行静的解析）は、PR コメントで `/request-review`
> を入力したタイミングでのみ実行されます。

##### 配布先向け静的解析 CI（任意）

push / PR 時にも静的解析したい場合は、wheel 同梱のテンプレートを配置する。配置元:
`ame_ai_review_system/templates/workflow/ci.yml`（pip インストール先の site-packages 配下）。配置先:
`.github/workflows/ci.yml`。

```bash
# site-packages 内のテンプレート位置を解決して配置する
TMPL=$(python -c "import ame_ai_review_system, os; print(os.path.join(os.path.dirname(ame_ai_review_system.__file__), 'templates', 'workflow', 'ci.yml'))")
mkdir -p .github/workflows
cp "$TMPL" .github/workflows/ci.yml
```

このテンプレートは `pre-commit run --all-files`
で静的解析フックを回す。AI レビューフック 3 種（`ai-skip-guard` ほか）は `/request-review`
側で実行されるため `SKIP` する。 `ts` / `text` preset の system フックは `node_modules/.bin`
を直接起動する（eslint / prettier / markdownlint-cli2 等）。`package.json` があれば `npm install`
が自動実行される。

使用する LLM エンジンの SDK を追加（オプション）。PyPI 非公開のため、extras ではなく個別パッケージとして導入する。

```bash
pip install claude-agent-sdk       # Claude Python SDK
pip install google-antigravity     # Antigravity (Gemini)
```

> [!NOTE] **CI ワークフロー連携**: 方式 A は `ame-ai-reviewer init` が reusable
> workflow の薄いラッパを生成する。方式 B は `.github/` をコピーする（従来方式）。

#### 方式 B: ディレクトリコピー（オフライン・細かなカスタマイズ向け）

本リポジトリの以下のディレクトリを、導入先のリポジトリのルートに丸ごとコピーする。

- `.github/`
- `ame_ai_review_system/`

```bash
cp -r .github/ <your-repo>/
cp -r ame_ai_review_system/ <your-repo>/
```

##### CI ワークフロー差し替え時の chicken-and-egg 対策 (Issue #116)

GitHub Actions のイベントごとに実行する workflow ファイルの取得元は非対称です。

- `issue_comment`（`/request-review` のトリガー）→ **default ブランチ** の workflow が実行される
- `pull_request_review_comment`（インライン返信のトリガー）→ **PR ヘッドブランチ**
  の workflow が実行される

そのため、workflow 差し替えの移行 PR 中は `/request-review`
が main の旧 workflow を呼び失敗することがあります。例: vendored パッケージ削除と組み合わせた移行で
`No module named ame_ai_review_system`。対策は以下のいずれかです。

1. **ブートストラップ PR**: 最初に workflow 変更のみを main へ取り込む独立した PR を作る。main に新 workflow が入ってから、機能変更の PR を進める。
2. **`workflow_dispatch` で明示起動**: `--ref` に PR ブランチを指定して新ラッパを実行する。

       gh workflow run "AI Code Review (Command)" --ref <PRブランチ> -f pr_number=<N>

3. **返信経由のレビューで回避**: インライン返信は PR ヘッドブランチの workflow が実行されるため、移行 PR では返信判定（`AI Review Reply`）だけ先に検証できる。

### Step 2: AI エージェント用スキル（review-round）の導入（推奨）

専用スキルを `.claude/skills/review-round/SKILL.md` に配置します。これにより OpenCode / Claude
Code などの AI エージェントが Dual-Gate レビューラウンドを自律的に完遂できます。

Gate 1（pre-commit）と Gate
2（PR のスレッド解決ループ）を連続して実行します。本スキルは運用ルール（`SKIP=ai-precommit-review` /
`--no-verify` の禁止など）を AI エージェント向けにまとめた指示書です。詳細は
[instructions.md](instructions.md) / [CLAUDE.md](../../CLAUDE.md) を参照してください。

#### 方式 A の場合（wheel インストール時）

```bash
mkdir -p .claude/skills/review-round
curl -fsSL https://raw.githubusercontent.com/AME-Team/AME-AI-Review-System/v0.1.0/.claude/skills/review-round/SKILL.md \
  -o .claude/skills/review-round/SKILL.md
```

URL の `v0.1.0` は Step 1 で指定した `--ref` と同じリリースタグに揃えること。

#### 方式 B の場合（ディレクトリコピー時）

`.github/` / `ame_ai_review_system/` に加え、`.claude/skills/review-round/` もコピーする。

```bash
mkdir -p <your-repo>/.claude/skills
cp -r .claude/skills/review-round <your-repo>/.claude/skills/review-round
```

> [!NOTE] 配置先は `.claude/skills/review-round/SKILL.md`（[Agent Skills](https://agentskills.io)
> 標準のプロジェクトスキル配置場所。Claude Code が `.claude/skills/`
> 配下を自動的に読み込む）。CI 上の API 呼び出しは `GITHUB_REPOSITORY` / `GITHUB_API_URL`
> を自動参照するため、フォークや別リポジトリでも書き換えなしで動作する。

### Step 3: レビュアー用 GitHub App の作成と Secret 登録

1. GitHub 上で AI レビュアー用の GitHub App を作成する。作成画面は [Settings] → [Developer settings]
   → [GitHub Apps] → [New GitHub App]。App name は任意（例: `ame-ai-reviewer`）。
2. App の権限を設定する（インストール時または App 設定画面で）。
   - **Repository permissions**
     - `Contents`: Read-only（PR checkout 用）
     - `Pull requests`: Read & Write（レビュー/返信投稿用）
     - `Issues`: Read & Write（Issue コメント投稿用）
3. 作成後、App 設定画面で **Private key** を生成し、`.pem` ファイルをダウンロードする。
4. App を対象リポジトリにインストールする。
5. 導入先リポジトリの **[Settings] → [Secrets and variables] → [Actions] → [Secrets]**
   から以下を追加する。
   - `AME_AI_REVIEWER_APP_ID` : GitHub App の App ID（数値。App 設定画面に表示される）
   - `AME_AI_REVIEWER_APP_PRIVATE_KEY` : 手順 3 でダウンロードした `.pem` ファイルの内容全体

> [!NOTE] 本リポジトリのワークフロー（`review_command.yml` / `review_reply.yml`）は
> `actions/create-github-app-token@v2` を使い、上記 Secret から都度インストールトークンを発行して
> `GITHUB_PAT_TOKEN` / `AME_AI_REVIEWER_TOKEN`
> env 変数に設定します（Python コードは PAT/App の違いを意識せず動作します）。別のレビュアーを追加する場合は
> `<REVIEWER_NAME_UPPER>_APP_ID` / `<REVIEWER_NAME_UPPER>_APP_PRIVATE_KEY`
> の命名規則で Secret を追加してください（[カスタマイズガイド](customization.md)参照）。
>
> [!IMPORTANT] ローカル開発で `pre-commit` 時の AI レビューを利用する場合は、従来通り
> `~/.config/ame-ai-review-system/<name>.token`（PAT）または環境変数 `GITHUB_PAT_TOKEN` /
> `<NAME>_TOKEN` を使います。CI のみ GitHub App 認証に切り替わっています。

### Step 4: ワークフローの設定確認と修正

`.github/workflows/review_command.yml` および `review_reply.yml` を開き、環境変数を変更します。

```yaml
env:
  REVIEWER_NAME: ame-ai-reviewer # 作成したレビュアーのアカウント名と一致させる
```

### Step 5: 動作設定（`config.json`）

`ame_ai_review_system/config.json` でレビューの動作を制御します。

```json
{
  "precommit_review_enabled": true,
  "precommit_require_static_checks": true,
  "precommit_engine": "auto"
}
```

| キー                              | デフォルト | 説明                                                                                                                                                                                                                                                                                                                                                                    |
| --------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `precommit_review_enabled`        | `true`     | `true` にすると `git commit` 時にローカルで AI レビューが走り、指摘があればコミットをブロックする。                                                                                                                                                                                                                                                                     |
| `precommit_require_static_checks` | `true`     | `true` の場合、AI レビュー実行前にプロジェクトの pre-commit フックで staged ファイルを検査し、全て pass した場合のみ AI レビューを実行する。pre-commit フレームワーク経由で実行される際は実フックが既に強制済みのため再実行しない（Issue #55 I2）。                                                                                                                     |
| `precommit_max_reviews`           | `3`        | pre-commit レビュー (Gate 1) の重大度によらない総レビュー回数ハード上限。blocking 指摘（MIDDLE 以上）が残っていても、この回数に達したらコミットを許可して警告を出力する（Issue #134）。LOW/INFO のみ連続の escape は固定 2 回で別途働く。<br>PR 側の総レビュー回数上限は `pr_max_reviews` で設定。`0` 以下・不正値は既定 `3`、LOW 連続閾値（2）以下は `3` にクランプ。  |
| `pr_max_reviews`                  | `3`        | PR レビュー (Gate 2) の総レビュー回数のハード上限。LOW 連続の有無に関わらず、この回数に達したら以降のレビューはスキップし Gate 2 を終了する（Issue #129）。到達時は PR に一度だけ通知コメントが投稿される。`0` 以下・不正値は既定 `3`。                                                                                                                                 |
| `precommit_engine`                | `"auto"`   | pre-commit レビューのエンジン。`"auto"` で実装に使っているツールを自動検出。`"claude"` / `"opencode"` / `"antigravity"` で明示指定も可。                                                                                                                                                                                                                                |
| `precommit_model`                 | (なし)     | pre-commit レビューのモデルを明示指定。省略時はエンジン既定値。`opencode` はサーバー既定モデルが使われる（実装で使っているモデルを自動解決する機能はない。Issue #55 B3）。                                                                                                                                                                                              |
| `precommit_thinking`              | (なし)     | pre-commit レビューの思考量。省略時は PR の `thinking` を継承。                                                                                                                                                                                                                                                                                                         |
| `precommit_review_budget_usd`     | (なし)     | pre-commit レビュー専用の予算 (Claude のみ効果)。省略時は PR の `review_budget_usd` を継承。                                                                                                                                                                                                                                                                            |
| `sdk_lang`                        | `"python"` | SDK 言語。Claude エンジンのみ有効で `"python"` / `"typescript"` を切替え（環境変数 `REVIEW_SDK_LANG` / 後方互換 `CLAUDE_SDK_LANG` でも指定可）。`opencode` は TypeScript、`antigravity` は Python で固定。                                                                                                                                                              |
| `review_include_package_dir`      | `false`    | 移植先で vendored した `ame_ai_review_system/` 配下を AI レビュー対象にするか (Issue #37)。既定は対象外 (既にレビュー済みのため)。`true` にすると対象になる。対象外でも、`.pre-commit-config.yaml` や README などから `ame_ai_review_system.*` を参照している変更をレビューする際は、パッケージがリポジトリに存在する旨の注記がプロンプトに自動付与される (Issue #47)。 |
| `review_repair_model`             | (なし)     | 壊れたレビュー JSON を修復する際に使うモデル。省略時は本体と同じモデル。弱いモデルが JSON を壊す場合に、より強いモデルを指定すると修復成功率が上がる。修復は最大 3 回試行される（`review_repair_attempts`、既定 3）。                                                                                                                                                   |
| `show_engine_info_gate1`          | `true`     | pre-commit レビュー (Gate 1) でエンジン・モデル・思考量のバナーを表示するか (Issue #40)。`false` で非表示 (非 Claude エンジンの budget 未強制警告も抑止)。                                                                                                                                                                                                              |
| `show_engine_info_gate2`          | `true`     | PR レビュー (Gate 2) でエンジン・モデル・思考量のバナーを表示するか (Issue #40)。`false` で非表示 (非 Claude エンジンの budget 未強制警告も抑止)。CI ログに表示される値は Variables / Secrets で制御する。                                                                                                                                                              |

> [!NOTE] **pre-commit AI レビューのエンジン自動検出** `precommit_engine: "auto"`
> (既定) の場合、pre-commit フックが自身のプロセスツリーを親方向へたどり、`opencode` / `claude` /
> `agy` (Antigravity) のいずれかを検出します。例えば OpenCode セッション内で `git commit`
> すると、自動的に OpenCode でレビューが走ります。モデルは `precommit_model` /
> `PRECOMMIT_REVIEW_MODEL`
> が未指定の場合は OpenCode のサーバー既定モデルが使われます (実装で使っているモデルは自動解決されません。Issue
> #55 B3)。PR レビューとは独立して環境変数 `PRECOMMIT_REVIEW_ENGINE` / `PRECOMMIT_REVIEW_MODEL`
> でも上書き可能です。
>
> **無限ループ回避**: pre-commit レビュー (Gate 1) には 2 つの独立した escape 機構がある（Issue
> #134）。
>
> 1. LOW レベルの指摘のみが**固定 2 回**連続したらコミットを通す。
> 2. 重大度によらず総レビュー回数が `precommit_max_reviews`（既定 `3`
>    回）に達したら、blocking 指摘が残っていてもコミットを通して警告を出力する。
>
> コミット成功時に streak カウンタは 0 にリセットされる（post-commit フック）。エンジン失敗時は fail-closed でコミットをブロックする。PR 側の総レビュー回数は
> `pr_max_reviews`（既定 `3` 回）が上限（Issue #129）。
>
> **vendored パッケージ参照の注記 (Issue #47)**: `review_include_package_dir: false`（既定）で
> `ame_ai_review_system/`
> をレビュー差分から除外する運用では、`.pre-commit-config.yaml`（`python3 -m ame_ai_review_system.skip_guard`
> 等）や README が参照するモジュールが diff に見えないため、モデルが「モジュール不存在」と誤判定してコミットをブロックする場合がある。これを防ぐため、差分・変更ファイルが除外対象パッケージを参照し、かつ実体がリポジトリに存在する場合、プロンプトに「vendored 済み・レビュー対象外」の注記を自動付与する。初回導入コミットのようにパッケージ本体を一括追加する場合は、`review_include_package_dir: true`
> にすると本体もレビュー対象にできる。
>
> **前段の静的解析が必須** `precommit_require_static_checks: true`
> (既定) の場合、AI レビュー実行前に ruff check / ruff format --check /
> mypy を staged された Python ファイルに対して実行し、全て pass した場合のみ AI レビューを実行します。LLM
> API コストの節約と、フォーマット違反などの単純な指摘の AI レビューへの回送を防ぐための仕組みです。

### Step 6: ユーザー固有設定（`config.user.json`・任意）

環境依存の設定（エンジン・モデル・思考量など）は `ame_ai_review_system/config.user.json`
に記述できます。このファイルは **Git 管理対象外**（`.gitignore` に登録済み）で、`config.json`
より優先されます。存在しない場合は無視されます。

```json
{
  "precommit_engine": "claude",
  "precommit_model": "sonnet",
  "precommit_thinking": "medium"
}
```

> [!TIP] 環境変数 `AME_REVIEW_USER_CONFIG` で `config.user.json` のパスを変更できます。

### Step 7: グローバル設定（`~/.config/ame-ai-review-system/config.json`・任意）

複数リポジトリに共通する Gate
1 のエンジン・モデル・思考量は、ユーザー単位のグローバル設定で指定できます (Issue #120)。

```json
{
  "precommit_engine": "claude",
  "precommit_model": "sonnet",
  "precommit_thinking": "medium"
}
```

- 配置先: `~/.config/ame-ai-review-system/config.json`
- パスは環境変数 `AME_REVIEW_GLOBAL_CONFIG` で変更できる。
- 取り込まれるのは Gate 1 の `precommit_*` キーに加え、エンジン解決用のレガシー `engine`
  キーも対象である (Issue #126)。
- 優先順位は **環境変数 > リポジトリ設定 > グローバル設定 > 継承（自動検出）** である。
- エンジンもモデルと同じ優先順位で解決される (Issue #126)。リポジトリ設定の
  `precommit_engine: "auto"`
  は「未指定」として扱われ、グローバル設定の具体エンジンを覆わない。具体エンジンが無い場合のみ自動検出に進む。
- レガシー `engine` キーがリポジトリ設定に明示されていれば、`precommit_engine: "auto"`
  の「未指定」より優先される。既定 `claude` が自動検出の代わりに採用される。

> [!NOTE] 詳細は [カスタマイズガイド §5-2](customization.md) を参照してください。

---

## 3. 動作確認

### 3-1. ローカルでの動作確認（Gate 1: pre-commit ゲート）

1. **静的解析の検証**
   - Pythonファイル等に適当なフォーマット崩れや構文エラーを意図的に含め、`git add` してから
     `git commit -m "test"` を実行する。
   - `ruff check` や `mypy`
     などの前段の静的解析でコミットがブロックされ、AIレビューが実行されないことを確認する。
2. **AIレビューの検証**
   - 静的解析エラーを修正して `git commit` を実行する。
   - 静的解析がすべて PASS し、`AI Code Review (pre-commit)`
     フックが実行され、LLMによるコードレビューが走ることを確認する。
   - 指摘事項がある場合、コミットがブロックされ、指摘内容が表示されることを確認する。
3. **streak機能の検証**
   - コミットがブロックされた後、コードを微修正して再度コミットを繰り返す。
   - `LOW`
     レベル以下の軽微な指摘のみが連続し、**固定 2 回**に達したら、escape でコミットが通ることを確認する。
   - blocking 指摘が残り続ける場合も、総レビュー回数が
     `precommit_max_reviews`（既定 3 回）に達したらコミットが通り、警告が出力される（Issue #134）。

### 3-2. CI/CD環境での動作確認（Gate 2: PR ゲート）

> [!NOTE] **Gate 2 の起動経路は 2 通り**。reusable workflow の `pr_number` 入力は `type: string`
> で受け取るため、issue_comment（PR コメント）・workflow_dispatch（手動実行）のどちらでも配布先ラッパは
> `fromJSON()` に依存せずそのまま渡せる (Issue #104)。内部の CLI（`argparse type=int` /
> `int()`）が数値へキャストする。

1. **静的解析 Circuit Breaker の検証**
   - 静的解析エラー（Linter警告や型エラー）を含んだコードを、`SKIP`
     変数を用いてコミットし、プッシュして PR を作成する。

     ```bash
     # 静的解析フック（ruff/mypy/semgrep）のみをスキップしてコミット
     SKIP=ruff,mypy,semgrep-custom git commit -m "test: verify circuit breaker"
     ```

     > [!WARNING] この `SKIP` 指定コミットは Circuit
     > Breaker 動作確認専用である。通常の開発では使用しない。

   - PR コメントで `/request-review` を入力する。
   - PR に静的解析エラーが存在する場合、`static_precheck.py`（Circuit
     Breaker）がそれを検知し、AI レビューをスキップすることを確認する。
2. **AIレビューと対話サイクルの検証**
   - PR上のすべての静的解析エラーを解消してプッシュする。
   - 再度 PR コメントで `/request-review`（または `/review`）を入力する。
   - `AI Code Review (Command)`
     ジョブが起動し、PR にインラインコメント（レビュー）が投稿されることを確認する。
3. **返信とResolveの検証**
   - 投稿されたコメントのスレッドに対して、修正を加えた後に `@ame-ai-reviewer[bot] 修正しました`
     のように**インライン返信**する。
   - `AI Review Reply` ジョブが起動し、**そのスレッドだけ**に自動的に `LGTM`
     または追加指摘が返答されることを確認する（1 返信 = 1 LGTM）。
   - `LGTM` が届いたスレッドを「Resolve（解決済み）」に変更し、全スレッド Resolve 後に再度
     `/request-review` で再レビューを依頼する。
4. **手動実行（workflow_dispatch）経由の検証** — Issue #104
   - Actions タブで `AI Code Review (Command)` を選択し **[Run workflow]** をクリックする。
   - `pr_number` 入力欄に任意の PR 番号（例: `9`）を入力して実行する。
   - `workflow_dispatch` の inputs は常に文字列になる。しかし reusable workflow が `type: string`
     で受け取るため、ジョブ生成前の型検証で失敗しないこと（旧: `Unexpected value '9'`）を確認する。
   - 数字以外（例:
     `abc`）を渡した場合は、ジョブ生成時の型検証の代わりに実行時の CLI（`argparse type=int`）がエラー終了する。`pr_number`
     には数値のみ指定すること。
   - レビューが正常に投稿されるまで確認する（issue_comment 経由と同一の処理パス）。
   - 手動実行時は `github.event.comment` が無いため、コマンドは既定の `/request-review`
     として扱われて判定が通る (Issue #71)。

### 3-3. ランディングページの起動確認

本リポジトリに同梱されている Vite ベースのランディングページ（紹介サイト）の起動・動作確認手順です。

1. **開発用サーバーの起動** リポジトリのルートディレクトリで以下を実行する。

   ```bash
   npm run dev --workspace=landing-page
   ```

2. **ブラウザでの確認** ブラウザで `http://localhost:5173`
   を開き、インタラクティブなコミットシミュレーターや各種設定スニペットの切り替え表示が正しく動作することを確認する。
3. **本番用ビルドとプレビュー（任意）**
   本番用にコンパイルしてローカルでプレビューする場合は、以下を実行する。

   ```bash
   # ビルドを実行
   npm run build --workspace=landing-page
   # ビルド成果物をプレビュー (http://localhost:4173)
   npm run preview --workspace=landing-page
   ```

   詳細な起動・開発手順については、[landing-page/README.md](../../landing-page/README.md)
   も参照すること。
