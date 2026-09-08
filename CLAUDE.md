# Claude Code ルール — AME-AI-Review-System

## ブランチ・PR ポリシー（必須）

### マージフロー

```text
feature/* | bug/* | chore/*  ──►  main
         作業ブランチ              リリース
```

### PR のデフォルト base

- **AI Agent が PR を作成する際のデフォルト base は `main` とする。**
- `gh pr create --base main --head <ブランチ名>` の形式で作成すること。

### 禁止事項

- `gh pr create` の `--base` を省略しない。

## PR レビュー対応フロー（必須）

PR をマージする前に、以下のフローをすべて完了すること。

### 1. インラインレビューコメントへの対応と返信

PR に AI レビュアーからインラインレビューコメントが付いたら、次の手順を実施する。対象レビュアー:
`ame-ai-reviewer` (GitHub App のため、コメント作成者は `ame-ai-reviewer[bot]` になる)。

1. **コードを修正する** — CRITICAL / HIGH / MIDDLE /
   LOW レベルの各指摘事項に対応した修正を加え、pre-commit を通過させてコミット・プッシュする。
2. **各スレッドに返信する** — 対応内容を説明したメッセージを、必ず `@<レビュアー名>[bot]`
   メンション付きで投稿する。
   - API: `POST /repos/{owner}/{repo}/pulls/{pr}/comments/{id}/replies`
   - トークン: `~/.config/ame-ai-review-system/github.token`（ユーザーアカウント）
3. **レビュアーが LGTM 返信してくれる** — レビュアーが対応済みを確認し、返信を投稿してくれる。
   - CI 上のレビュアーは GitHub App (`AME_AI_REVIEWER_APP_ID` /
     `AME_AI_REVIEWER_APP_PRIVATE_KEY`) から発行されたインストールトークンを使用
   - 本文例: `「対応確認しました。LGTM ✅ Resolve してください。」`
4. **スレッドを Resolve する** — LGTM 返信が来たら Resolve する。
   - GitHub REST には対応エンドポイントが無い。GraphQL mutation `resolveReviewThread`
     経由で Resolve する。実装は `reply.py` → `github_client.resolve_review_thread` で行う。

### 2. 返信・Resolve の API まとめ

```text
GitHub API : https://api.github.com
GraphQL   : https://api.github.com/graphql
リポジトリ : AME-Team/AME-AI-Review-System
通常トークン : ~/.config/ame-ai-review-system/github.token（なければ環境変数 $GITHUB_PAT_TOKEN を使用）

CI 上のレビュアートークン（GitHub App インストールトークンを actions/create-github-app-token で取得）:
  AME_AI_REVIEWER_APP_ID          : GitHub App の App ID（数値）
  AME_AI_REVIEWER_APP_PRIVATE_KEY : Private Key (.pem)

ローカル環境のレビュアートークン:
  ame-ai-reviewer : ~/.config/ame-ai-review-system/ame-ai-reviewer.token

スレッド返信 : POST /repos/{repo}/pulls/{pr}/comments/{id}/replies
Resolve     : GraphQL mutation resolveReviewThread(input: {threadId: ID!})
```

> **トークン取得の優先順位（ファイルが存在しない場合は次を試す）**
>
> 1. `~/.config/ame-ai-review-system/github.token`（またはレビュアー固有の `<name>.token`）
> 2. 環境変数 `$GITHUB_PAT_TOKEN`（または `<NAME>_TOKEN`）
>
> GitHub Actions 上では `actions/create-github-app-token@v2` がインストールトークンを発行し、それを
> `GITHUB_PAT_TOKEN` / `AME_AI_REVIEWER_TOKEN` に設定して Python コードに渡す。`GITHUB_REPOSITORY` /
> `GITHUB_API_URL`
> が自動設定されるため、ワークフロー側での環境変数明示は不要（`github_client.resolve_env`
> が解決する）。

### 3. 各レビュアーの仕様（重要）

各レビュアーは以下の 2 つのタイミングで動作する。

1. **レビュー実行**: PR コメントで `/request-review`
   が入力されたときにインラインコメントを投稿する（`review_command.yml`）。`/review`
   も同じコマンドのエイリアス。
2. **返信判断**: インライン返信（`pull_request_review_comment: created` イベント）で
   `@<レビュアー名>`
   宛ての返信を検知する。**トリガーとなったスレッド 1 件だけに**、実際の diff を読んで LGTM か追加指摘かを判断して返信する（`review_reply.yml`、1 返信 =
   1 LGTM / Issue #39）。ただし `/`
   で始まるコメント（コマンド）は返信判定の対象外。PR 本文コメント（`issue_comment`）では発火しない。

返信判断は `reply.py` (`python3 -m ame_ai_review_system.reply run`) → Claude
Sonnet のフローで実行される。Claude はレビュアーとして「元の指摘内容」「開発者の返信」「PR の diff」を照合し、修正が十分かを判断する。

### 4. PR 作成後の自動レビュー対応フロー

> **【絶対ルール】未解決スレッドがゼロになるまで絶対に作業を止めない。**
> ユーザーから「止めていい」と明示的に言われない限り、何があっても以下のループを継続する。途中で止めることは厳禁。

PR を作成・プッシュしたら、以下のループを完遂すること。

0. PR コメントで `/request-review` を投稿してレビューを依頼する（`github.token`）。 `/review`
   も同じ意味。
1. `ame-ai-reviewer[bot]` のインラインコメント一覧を取得する。API:
   `GET /repos/{repo}/pulls/{pr}/comments`。
2. 未対応の CRITICAL / HIGH / MIDDLE / LOW コメントがあればコードを修正してコミット・プッシュする
3. 各スレッドに `@ame-ai-reviewer[bot]` メンション付きで対応内容を返信する（`github.token`）
4. `ame-ai-reviewer[bot]` が LGTM 返信を投稿してくれる（`ame-ai-reviewer.token`
   または CI 上の App インストールトークン）
5. LGTM が届いたスレッドを Resolve する
6. **未解決スレッドが残っていれば 1 に戻る**
7. 全スレッドが Resolve されたら、**再度 `/request-review`
   を投稿して再レビュー**する。新たな指摘がなければ完了。指摘があれば 1 に戻り、指摘がゼロになるまでループする。

### 5. CI/CD 品質ゲートの例外ルール

`main.py review` は指摘があっても `exit 0` で終了させる（ワークフローを success にする）。

- **理由**:
  AI レビューの指摘によるエラーと、スクリプト自体のエラーを区別できるようにするため。指摘は GitHub の PR インラインコメントで通知されるため、CI ステータスでゲートする必要はない。
- **適用範囲**: `main.py review`
  の末尾 exit ステータスのみ。スクリプト内のエラー（Claude 呼び出し失敗など）は引き続き `exit 1`
  を返す。

### 7. レビュアー追加方法

レビュー処理は `main review` サブコマンドが担う。`REVIEWER_NAME` / `REVIEWER_PROMPT_FILE`
環境変数でパラメータ化されているため、コード追加なしで新レビュアーを追加できる。

1. GitHub App を作成し、対象リポジトリにインストール。必要権限: `Contents: Read` /
   `Pull requests: Read & Write` / `Issues: Read & Write`
2. GitHub Actions Secrets に `<REVIEWER_NAME_UPPER>_APP_ID` と
   `<REVIEWER_NAME_UPPER>_APP_PRIVATE_KEY` を登録（例: `SECURITY_REVIEWER_APP_ID` /
   `SECURITY_REVIEWER_APP_PRIVATE_KEY`）
3. `.github/workflows/review_command.yml`（コマンドトリガー・標準）と `review_reply.yml`
   に新ジョブを追加する。`review_command.yml` / `review_reply.yml` の**既存全ジョブの `if`
   条件にも新レビュアー名を追加**する（カスケードループ防止）
   - 現在のレビュアーは `ame-ai-reviewer`（App bot login は `ame-ai-reviewer[bot]`）。`if` 条件に
     `github.event.comment.user.login != '<新レビュアーslug>[bot]'` を追加する
4. プロンプトファイル `ame_ai_review_system/<レビュアー名>_prompt.txt` を作成

### 8. コーディング規約（レビューでよく指摘される点）

- コメントは **WHY のみ**。WHAT を説明するコメント・docstring は不要
- `except Exception:` は禁止。発生しうる具体的な例外型に限定する
- `kill -15 $pids` は禁止。`echo "$pids" | xargs -r kill -15` を使う
- 一時ファイルは必ず `cleanup()` + `trap cleanup EXIT` で管理する
- シェルで外部入力を扱う場合は `printf '%s\n'`
  または stdin 渡しを使い、引数展開によるインジェクションを避ける

> 上記規約は Semgrep カスタムルール (`ame_ai_review_system/.semgrep/rules.yml`) で機械的に検出・ブロックする。新しい規約を追加する場合は:
>
> 1. `ame_ai_review_system/.semgrep/rules.yml` にルールを追加
> 2. `pre-commit run semgrep-custom` で検証
> 3. 既存コードに違反があれば修正

### 9. トークン削減施策（Issue #16）

以下の施策により AI レビューのラウンド数・トークン消費量・処理時間を削減する。

- **Circuit Breaker**:
  PR レビュー前に ruff/mypy/semgrep を実行する。エラーがあれば AI レビューをスキップする。`pr_review_require_static_checks`
  で ON/OFF。
- **プロンプトキャッシュ最適化**: 返信判定プロンプトは固定セクションを先頭に配置する。
- **Reasoning Effort 制御**: 返信判定は `reply_model`/`reply_thinking`
  で軽量モデルに切り替え、推論トークンを削減する。
- **Stale-Loop 検出**: レビュアーの直近2返信の Jaccard 類似度 ≥80% で強制 LGTM。
- **Diff 圧縮**: `diff_utils.py` が git diff のメタデータ・バイナリ差分・連続空行を除去。
- **最大ラウンド制限**: PR ごとの総レビュー回数は
  `pr_max_reviews`（既定 3 回）。上限到達時は PR に一度だけ通知コメントを投稿して Gate
  2 を終了する。3 ラウンド目以降（`review_count >= 2`）に収束シグナルを挿入。
