import React from "react";
import { type Locale, type TranslationResource } from "./i18n";
import { type FontStyle } from "./assets/headerImage";
import { getHeaderImageSvg } from "./assets/headerImage";
import { type DocPageId } from "./docsNav";
import {
  StaticAnalysisSection,
  EngineComparisonSection,
  DualGateFlowDiagram,
  PipelineDiagram,
  Simulator,
  ConfigTabs,
} from "./components";

/* ------------------------------------------------------------------ */
/* Doc primitives                                                      */
/* ------------------------------------------------------------------ */

const DocH1: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight leading-tight">
    {children}
  </h1>
);

const DocH2: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <h2 className="text-xl font-bold text-gray-900 dark:text-white border-b border-gray-200 dark:border-gray-800 pb-2">
    {children}
  </h2>
);

const DocH3: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <h3 className="text-base font-bold text-gray-900 dark:text-white">{children}</h3>
);

const DocP: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <p className="text-sm md:text-base text-gray-600 dark:text-gray-400 leading-relaxed">
    {children}
  </p>
);

const DocInline: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <code className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-primary dark:text-primary font-mono text-[0.85em]">
    {children}
  </code>
);

const DocPre: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <pre className="bg-gray-950 rounded-md border border-gray-900 dark:border-gray-800 p-5 overflow-x-auto text-xs font-mono text-gray-300 leading-relaxed whitespace-pre">
    {children}
  </pre>
);

const DocNote: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="border-l-4 border-primary/40 bg-primary/5 px-4 py-3 rounded-r-md text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
    {children}
  </div>
);

const DocWarning: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="border-l-4 border-grounded-orange/50 bg-grounded-orange/5 px-4 py-3 rounded-r-md text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
    {children}
  </div>
);

const DocTable: React.FC<{
  head: string[];
  rows: React.ReactNode[][];
}> = ({ head, rows }) => (
  <div className="overflow-x-auto rounded-md border border-gray-200 dark:border-gray-800">
    <table className="w-full text-left text-xs md:text-sm">
      <thead>
        <tr className="bg-gray-100 dark:bg-gray-850 text-gray-700 dark:text-gray-300">
          {head.map((h) => (
            <th
              key={h}
              className="px-3 py-2.5 font-semibold border-b border-gray-200 dark:border-gray-800 whitespace-nowrap"
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr
            key={i}
            className="odd:bg-white even:bg-gray-50 dark:odd:bg-gray-900 dark:even:bg-gray-850 text-gray-600 dark:text-gray-400"
          >
            {row.map((cell, j) => (
              <td
                key={j}
                className="px-3 py-2.5 border-b border-gray-100 dark:border-gray-800 align-top"
              >
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const DocList: React.FC<{ items: React.ReactNode[]; ordered?: boolean }> = ({ items, ordered }) => {
  const cls = "flex flex-col gap-2 pl-5 list-disc marker:text-primary text-sm md:text-base";
  const clsOl = "flex flex-col gap-2 pl-5 list-decimal marker:text-primary text-sm md:text-base";
  if (ordered === true) {
    return (
      <ol className={clsOl}>
        {items.map((item, i) => (
          <li key={i} className="text-gray-600 dark:text-gray-400 leading-relaxed">
            {item}
          </li>
        ))}
      </ol>
    );
  }
  return (
    <ul className={cls}>
      {items.map((item, i) => (
        <li key={i} className="text-gray-600 dark:text-gray-400 leading-relaxed">
          {item}
        </li>
      ))}
    </ul>
  );
};

const Section: React.FC<{
  title: string;
  children: React.ReactNode;
  id?: string;
}> = ({ title, children, id }) => (
  <section id={id} className="flex flex-col gap-4 w-full">
    <DocH2>{title}</DocH2>
    {children}
  </section>
);

const PageShell: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="flex flex-col gap-10 w-full">{children}</div>
);

/* ------------------------------------------------------------------ */
/* Overview                                                            */
/* ------------------------------------------------------------------ */

const OverviewPage: React.FC<{
  t: TranslationResource;
  locale: Locale;
  fontStyle: FontStyle;
  onNavigate: (id: DocPageId) => void;
}> = ({ t, locale, fontStyle, onNavigate }) => {
  const isJa = locale === "ja";
  const l = (ja: string, en: string): string => (isJa ? ja : en);
  return (
    <PageShell>
      <div
        role="img"
        aria-label={t.title}
        className="w-full rounded-lg shadow-md overflow-hidden"
        dangerouslySetInnerHTML={{ __html: getHeaderImageSvg(locale, fontStyle) }}
      />
      <div className="inline-flex items-center gap-2 bg-primary/10 border border-primary/20 text-primary px-3 py-1 rounded-md text-xs font-semibold w-fit">
        <span className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse"></span>
        <span>{t.badgeVersion}</span>
      </div>
      <div className="flex flex-col gap-4">
        <h1 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white tracking-tight leading-tight">
          {t.heroTitle1}
          <br />
          <span className="text-primary">{t.heroTitleAccent}</span>
          {t.heroTitle2}
        </h1>
        <DocP>{t.heroDesc}</DocP>
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => {
            onNavigate("demo");
          }}
          className="inline-flex items-center justify-center bg-primary hover:bg-primary-hover text-white text-sm font-semibold px-5 py-3 rounded-md transition-colors duration-150 shadow-sm"
        >
          {t.tryDemoBtn}
        </button>
        <button
          type="button"
          onClick={() => {
            onNavigate("config-json");
          }}
          className="inline-flex items-center justify-center border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 text-sm font-semibold px-5 py-3 rounded-md transition-colors duration-150"
        >
          {t.viewConfigBtn}
        </button>
      </div>

      <Section title={l("二重の品質ゲート（Dual-Gate）とは", "What is the Dual-Gate?")}>
        <DocP>
          {l(
            "本システムは「静的解析（Linter / 型検査）」と「AI レビュー」を融合し、ローカル（pre-commit）と CI（PR）の二重ゲートでコード品質を担保する、移植可能な開発フィロソフィー（IP アセット）パッケージです。",
            "This system fuses static analysis (linters / type checks) with AI review and enforces code quality through a dual gate spanning local (pre-commit) and CI (PR) — an easily portable development philosophy (IP asset) package."
          )}
        </DocP>
        <DocPre>
          {`[ ローカル開発 (Git Commit) ]
  └── Gate 1: pre-commit ゲート (静的解析 + AI レビュー)
        └── staged ファイルに対し ruff/mypy/semgrep 等を実行。パスした場合のみローカル AI レビューを実行。

[ CI/CD 環境 (Pull Request) ]
  └── Gate 2: PR ゲート (Circuit Breaker 静的解析 + AI レビュー)
        └── コメント \`/request-review\` 時に ruff/mypy/semgrep 等を実行。エラーが 0 件の場合のみ AI レビューを実行。`}
        </DocPre>
        <DocP>
          {l(
            "機械的な「Linter や型検査」を前段で実行し、無駄な LLM コストを削減する Circuit Breaker を備えています。ローカルで早期に検知する Shift-Left を徹底し、高品質なコードのみが PR に到達するよう強制します。",
            "Static checks run first as a Circuit Breaker to avoid wasteful LLM spend. Enforcing Shift-Left catches defects early so that only high-quality code reaches the PR."
          )}
        </DocP>
      </Section>

      <Section title={t.secFeaturesTitle}>
        <DocP>{t.secFeaturesDesc}</DocP>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <FeatureCard title={t.featureDiffTitle} desc={t.featureDiffDesc} icon="diff" />
          <FeatureCard title={t.featureCbTitle} desc={t.featureCbDesc} icon="bolt" />
          <FeatureCard title={t.featureGateTitle} desc={t.featureGateDesc} icon="shield" />
          <FeatureCard title={t.featureAgentTitle} desc={t.featureAgentDesc} icon="agent" />
          <FeatureCard title={t.featureLoopTitle} desc={t.featureLoopDesc} icon="loop" />
        </div>
      </Section>

      <Section title={l("次のステップ", "Next Steps")}>
        <DocList
          items={[
            <span key="a">
              {l("最初に導入作業を確認したい場合は ", "To start installing, see ")}
              <button
                type="button"
                onClick={() => {
                  onNavigate("quickstart");
                }}
                className="text-primary font-semibold hover:underline"
              >
                {t.pageQuickStart}
              </button>
              {l(" へ", ".")}
            </span>,
            <span key="b">
              {l("毎日の使い方を確認する場合は ", "For daily usage, see ")}
              <button
                type="button"
                onClick={() => {
                  onNavigate("gate1");
                }}
                className="text-primary font-semibold hover:underline"
              >
                {t.pageGate1}
              </button>
              {l(" / ", " / ")}
              <button
                type="button"
                onClick={() => {
                  onNavigate("gate2");
                }}
                className="text-primary font-semibold hover:underline"
              >
                {t.pageGate2}
              </button>
              {l(" へ", ".")}
            </span>,
            <span key="c">
              {l("設定を調整する場合は ", "To tune configuration, see ")}
              <button
                type="button"
                onClick={() => {
                  onNavigate("config-json");
                }}
                className="text-primary font-semibold hover:underline"
              >
                {t.pageConfigJson}
              </button>
              {l(" へ", ".")}
            </span>,
          ]}
        />
      </Section>
    </PageShell>
  );
};

const FeatureCard: React.FC<{ title: string; desc: string; icon: string }> = ({
  title,
  desc,
  icon,
}) => {
  const paths: Record<string, string> = {
    diff: "M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4",
    bolt: "M13 10V3L4 14h7v7l9-11h-7z",
    shield:
      "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
    agent:
      "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
    loop: "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15",
  };
  return (
    <div className="bg-white dark:bg-gray-850 p-5 rounded-md shadow-sm border border-gray-200/50 dark:border-gray-800 flex flex-col gap-3">
      <div className="w-9 h-9 rounded-md bg-primary/10 text-primary flex items-center justify-center">
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d={paths[icon] ?? paths["diff"]} />
        </svg>
      </div>
      <h3 className="text-sm font-bold text-gray-900 dark:text-white">{title}</h3>
      <p className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">{desc}</p>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* Features                                                            */
/* ------------------------------------------------------------------ */

interface FeatureDetail {
  title: string;
  bodyJa: string;
  bodyEn: string;
}

const FEATURE_DETAILS: FeatureDetail[] = [
  {
    title: "mainブランチとの全累積差分レビュー",
    bodyJa:
      "従来のコミット単位の差分チェックではなく、origin/{base}...HEAD（既定は origin/main...HEAD）の全累積差分を評価対象とします。複数コミットを含む PR でも変更の全容を漏らさず追跡・評価できます。",
    bodyEn:
      "Reviews the full cumulative diff (origin/{base}...HEAD, default origin/main...HEAD) instead of per-commit fragments, so even multi-commit PRs are evaluated in their entirety.",
  },
  {
    title: "静的サーキットブレーカー（Circuit Breaker）",
    bodyJa:
      "PR レビュー前に ruff / mypy / semgrep 等の静的解析を先行実行します。1 件でもエラーがあれば AI レビューをスキップして LLM トークン消費を抑制します。pr_review_require_static_checks で ON/OFF できます（既定 ON）。",
    bodyEn:
      "Runs static analysis (ruff / mypy / semgrep, etc.) before the PR review. Any error skips the AI review, saving LLM tokens. Toggle with pr_review_require_static_checks (default ON).",
  },
  {
    title: "二重品質ゲート（Dual-Gate）",
    bodyJa:
      "Gate 1（ローカル pre-commit）と Gate 2（CI/CD PR）の二段階で静的解析と AI レビューを実施します。欠陥の早期検出（Shift-Left）と PR での強固なガードを両立します。",
    bodyEn:
      "Runs static analysis plus AI review at both Gate 1 (local pre-commit) and Gate 2 (CI/CD PR), combining early Shift-Left detection with a strong PR guard.",
  },
  {
    title: "マルチ Coding エージェント対応",
    bodyJa:
      "Claude Code / OpenCode / Antigravity CLI をエンジンとして指定できます。Coding エージェントは差分外領域も自発的に探索し、「コード修正に伴うドキュメント更新の有無」なども高度に検証します。",
    bodyEn:
      "Claude Code, OpenCode, or Antigravity CLI can be selected as the engine. The coding agent also explores beyond the diff, validating things like whether documentation updates accompany code changes.",
  },
  {
    title: "コマンド駆動のレビュー",
    bodyJa:
      "PR コメントで /request-review（エイリアス: /review）を入力したタイミングでレビューが走ります。",
    bodyEn: "Reviews are triggered by posting /request-review (alias: /review) in the PR comments.",
  },
  {
    title: "pre-commit 時の AI レビュー（Gate 1）",
    bodyJa:
      "git commit 時にローカルで AI レビューが走り、指摘があればコミットをブロックします（既定 ON）。PR レビューと同じプロンプトを使用し、LOW レベル指摘のみ 2 回連続で PASS となるエスケープハッチを用意しています。前段の静的解析（ruff / mypy / semgrep）が全て pass した場合のみ AI レビューします。precommit_require_static_checks で ON/OFF できます（既定 ON）。",
    bodyEn:
      "Runs a local AI review on git commit and blocks the commit when issues are found (default ON). Uses the same prompt as PR review, with an escape hatch that PASSes after 2 consecutive LOW-only reviews. AI review runs only when the upstream static checks (ruff / mypy / semgrep) all pass. Toggle with precommit_require_static_checks (default ON).",
  },
  {
    title: "Semgrep カスタムルール",
    bodyJa:
      "CLAUDE.md §8 のコーディング規約（broad exception catch 禁止、kill -15 $pids 禁止、echo | python3 -c 禁止、SKIP バイパス禁止 等）を Semgrep の 8 ルールで機械的に検出します。ルールは ame_ai_review_system/.semgrep/rules.yml。",
    bodyEn:
      "Coding rules from CLAUDE.md §8 (no broad exception catch, no kill -15 $pids, no echo | python3 -c, no SKIP bypass, etc.) are detected mechanically by 8 custom Semgrep rules in ame_ai_review_system/.semgrep/rules.yml.",
  },
  {
    title: "プロンプトキャッシュ最適化",
    bodyJa:
      "返信判定プロンプトは固定セクションを先頭、動的セクション（diff / 返信）を末尾に配置し、Claude API のキャッシュヒット率を最大化します。",
    bodyEn:
      "Reply-judgement prompts place the fixed sections first and dynamic sections (diff / reply) last to maximize Claude API cache hit rates.",
  },
  {
    title: "Reasoning Effort の役割別制御",
    bodyJa:
      "レビュー時と返信判定時で model / thinking を個別設定できます（review_model / reply_model / review_thinking / reply_thinking）。返信判定は haiku / low など軽量設定で推論トークンを削減します。",
    bodyEn:
      "Model and thinking effort are configurable independently for review and reply judgement (review_model / reply_model / review_thinking / reply_thinking). Reply judgement uses lightweight settings (haiku / low) to cut reasoning tokens.",
  },
  {
    title: "Stale-Loop 検出（強制 LGTM）",
    bodyJa:
      "レビュアーが同じ指摘を言い換えて繰り返す膠着状態を Jaccard 類似度（既定閾値 0.80）で検出し、強制 LGTM で膠着を打破します。連続 non-LGTM が 3 回以上でも stale と判定します。",
    bodyEn:
      "Detects stalemates where the reviewer repeats the same findings (Jaccard similarity ≥ 0.80 by default) and breaks the loop with a forced LGTM. 3+ consecutive non-LGTM replies also count as stale.",
  },
  {
    title: "Diff 圧縮（RTK アプローチ）",
    bodyJa:
      "git diff のメタデータ行・バイナリ差分・連続空行を除去し、LLM 入力トークンを削減します。4000 行を超える diff は優先度付き切り捨て（priority / front / head_tail）で圧縮します。",
    bodyEn:
      "Strips diff metadata, binary diffs, and consecutive blank lines to cut LLM input tokens. Diffs over 4000 lines are truncated with a priority strategy (priority / front / head_tail).",
  },
  {
    title: "実装エンジンの自動検出",
    bodyJa:
      '実装に使っている AI ツールをプロセスツリーから自動検出します（precommit_engine="auto"）。OpenCode で実装していれば、同じ組み合わせでレビューします。config.json の precommit_* キーや環境変数で上書きできます。',
    bodyEn:
      'Auto-detects the AI tool used for implementation from the process tree (precommit_engine="auto"). If implemented with OpenCode, the review uses the same combination. Override via config.json precommit_* keys or environment variables.',
  },
  {
    title: "ユーザー固有設定オーバーライド",
    bodyJa:
      "config.user.json（Git 管理対象外）で環境依存の設定（エンジン・モデル・思考量など）を上書きできます。config.json より優先されます。",
    bodyEn:
      "Environment-specific settings (engine, model, thinking, etc.) can be overridden in config.user.json (not tracked by Git), taking priority over config.json.",
  },
  {
    title: "簡単移植",
    bodyJa:
      "wheel インストール（推奨）とディレクトリコピーの 2 方式を提供します。wheel 方式は ame-ai-reviewer init で設定・ワークフローを生成し、CI は reusable workflow を呼ぶ薄いラッパのため、更新は参照タグの差し替えのみです。",
    bodyEn:
      "Two installation options: wheel install (recommended) or directory copy. The wheel approach generates config and workflows via ame-ai-reviewer init; CI wrappers are thin, so upgrades are just a tag bump.",
  },
  {
    title: "対話型の修正サイクル",
    bodyJa:
      "開発者がインラインスレッドに @ame-ai-reviewer[bot] で返信すると、AI が最新コードを再評価してスレッドに返答します。LGTM を受け取ったスレッドは Resolve できます。",
    bodyEn:
      "When a developer replies with @ame-ai-reviewer[bot] in an inline thread, the AI re-evaluates the latest code and replies. Threads that receive LGTM can be resolved.",
  },
  {
    title: "重大度ラベル",
    bodyJa:
      "指摘を CRITICAL / HIGH / MIDDLE / LOW の 4 段階で分類します。CRITICAL / HIGH / MIDDLE は必須修正、LOW は改善提案として扱われます。",
    bodyEn:
      "Issues are categorized into CRITICAL / HIGH / MIDDLE / LOW. CRITICAL / HIGH / MIDDLE are blocking; LOW is treated as a non-blocking suggestion.",
  },
  {
    title: "最大ラウンド制限",
    bodyJa:
      "PR ごとのレビュー回数に上限（既定 3 回、config.json の pr_max_reviews で変更可）を設け、無限ループを防止します。3 ラウンド目以降には収束シグナルをプロンプトへ挿入します。",
    bodyEn:
      "A maximum number of review rounds per PR (default 3, configurable via pr_max_reviews in config.json) prevents infinite loops. A convergence signal is injected into the prompt from round 3 onward.",
  },
  {
    title: "複数レビュアー対応",
    bodyJa:
      "REVIEWER_NAME / REVIEWER_PROMPT_FILE 環境変数でパラメータ化されているため、ジョブを追加するだけで役割の異なる複数のレビュアーを追加できます。",
    bodyEn:
      "Parameterized via REVIEWER_NAME / REVIEWER_PROMPT_FILE, so multiple reviewers with different roles can be added just by adding a workflow job.",
  },
];

const FeaturesPage: React.FC<{
  t: TranslationResource;
  locale: Locale;
  onNavigate: (id: DocPageId) => void;
}> = ({ t, locale, onNavigate }) => {
  const isJa = locale === "ja";
  const l = (ja: string, en: string): string => (isJa ? ja : en);
  return (
    <PageShell>
      <DocH1>{t.pageFeatures}</DocH1>
      <DocP>{t.secFeaturesDesc}</DocP>
      <div className="flex flex-col gap-6">
        {FEATURE_DETAILS.map((feature) => (
          <div
            key={feature.title}
            className="flex flex-col gap-2 p-5 rounded-md bg-white dark:bg-gray-850 border border-gray-200/50 dark:border-gray-800"
          >
            <DocH3>{isJa ? feature.title : feature.title}</DocH3>
            <DocP>{isJa ? feature.bodyJa : feature.bodyEn}</DocP>
          </div>
        ))}
      </div>
      <DocNote>
        {l("設定の詳細は ", "See ")}
        <button
          type="button"
          onClick={() => {
            onNavigate("config-json");
          }}
          className="text-primary font-semibold hover:underline"
        >
          {t.pageConfigJson}
        </button>
        {l(" を参照してください。", " for configuration details.")}
      </DocNote>
    </PageShell>
  );
};

/* ------------------------------------------------------------------ */
/* Static analysis                                                     */
/* ------------------------------------------------------------------ */

const StaticAnalysisPage: React.FC<{ t: TranslationResource; locale: Locale }> = ({
  t,
  locale,
}) => {
  return (
    <PageShell>
      <DocH1>{t.pageStaticAnalysis}</DocH1>
      <DocP>{t.staticAnalysisDesc}</DocP>
      <StaticAnalysisSection t={t} locale={locale} />
      <DocNote>{t.staticAnalysisPortabilityNote}</DocNote>
    </PageShell>
  );
};

/* ------------------------------------------------------------------ */
/* Quick Start                                                         */
/* ------------------------------------------------------------------ */

const QuickStartPage: React.FC<{ t: TranslationResource; locale: Locale }> = ({ t, locale }) => {
  const isJa = locale === "ja";
  const l = (ja: string, en: string): string => (isJa ? ja : en);
  return (
    <PageShell>
      <DocH1>{t.pageQuickStart}</DocH1>
      <DocP>
        {l(
          "本システムは GitHub Release のタグ付き wheel を配布しています（PyPI 非公開）。他プロジェクトへの導入は非常にシンプルです。",
          "This system ships a tagged wheel via GitHub Releases (not published on PyPI). Importing it into another project is straightforward."
        )}
      </DocP>

      <Section title={l("1. コアの導入", "1. Install the core")}>
        <DocH3>
          {l("方式 A: wheel インストール（推奨）", "Option A: wheel install (recommended)")}
        </DocH3>
        <DocPre>
          {`pip install https://github.com/AME-Team/AME-AI-Review-System/releases/download/v0.1.0/ame_ai_review_system-0.1.0-py3-none-any.whl`}
        </DocPre>
        <DocP>
          {l(
            "uv を使う場合（pipx と同等の CLI ツール管理）も利用できます。",
            "uv (equivalent CLI tool manager to pipx) is also supported."
          )}
        </DocP>
        <DocPre>
          {`# 導入
uv tool install "ame-ai-review-system @ https://github.com/AME-Team/AME-AI-Review-System/releases/download/v0.1.0/ame_ai_review_system-0.1.0-py3-none-any.whl"

# アップグレード
uv tool upgrade "ame-ai-review-system" --from "https://github.com/AME-Team/AME-AI-Review-System/releases/download/v0.1.0/ame_ai_review_system-0.1.0-py3-none-any.whl"`}
        </DocPre>
        <DocWarning>
          {l(
            "pipx と uv はどちらも ~/.local/bin に同一バイナリ（ame-ai-reviewer）を配置するため共存できません。切り替え時は一方を uninstall してください。URL の v0.1.0 は例です。Releases ページの最新バージョンに置き換えてください。",
            "pipx and uv both place the same binary (ame-ai-reviewer) in ~/.local/bin, so they cannot coexist — uninstall one before switching. The v0.1.0 URL is an example; replace it with the latest release."
          )}
        </DocWarning>
        <DocP>
          {l(
            "設定・ワークフローを生成します。TS エンジン（opencode / claude-ts）を使う場合は --with-engines を付けます。npm 依存のインストールも自動化されます（.ame-review/engines-ts/ に展開）。",
            "Generate config and workflows. Use --with-engines for TS engines (opencode / claude-ts); npm dependencies are installed automatically into .ame-review/engines-ts/."
          )}
        </DocP>
        <DocPre>{`ame-ai-reviewer init --preset python --ref v0.1.0 --with-engines`}</DocPre>
        <DocTable
          head={[l("オプション", "Option"), l("説明", "Description")]}
          rows={[
            [
              <DocInline key="p">--preset</DocInline>,
              l(
                "pre-commit 静的解析セット（auto / full / python / text / ts / minimal）。auto（既定）は package.json と .ts/.tsx ソースの有無で ts か full を自動選択。ts プリセットは ./node_modules/.bin を直接起動するため事前に npm install が必要。",
                "pre-commit static analysis set (auto / full / python / text / ts / minimal). auto (default) picks ts or full based on package.json and .ts/.tsx sources. The ts preset launches ./node_modules/.bin directly, so run npm install first."
              ),
            ],
            [
              <DocInline key="r">--ref</DocInline>,
              l(
                "reusable workflow の参照（リリースタグ or ブランチ）。--no-workflow 指定時以外は必須。",
                "The reusable workflow reference (release tag or branch). Required unless --no-workflow is given."
              ),
            ],
            [
              <DocInline key="v">--version</DocInline>,
              l(
                "Gate 1（pre-commit AI フック）が参照する wheel のバージョン。省略時はインストール済みパッケージの __version__。release の wheel を #sha256= で内容固定して参照します。",
                "The wheel version referenced by the Gate 1 (pre-commit AI hook). Defaults to the installed package __version__. The released wheel is pinned by #sha256=."
              ),
            ],
            [
              <DocInline key="py">--python</DocInline>,
              l(
                "オフライン環境向け。指定すると Gate 1 フックを language: system で生成し Python インタープリタパスを埋め込みます。省略時は wheel 方式（language: python）で生成し絶対パスを埋め込みません。AME_INIT_PYTHON 環境変数でも system 方式に切り替わります。",
                "For offline environments. Generates the Gate 1 hook with language: system, embedding the Python interpreter path. When omitted, uses the wheel-based language: python without absolute paths. AME_INIT_PYTHON also switches to the system approach."
              ),
            ],
            [
              <DocInline key="nw">--no-workflow</DocInline>,
              l(
                "CI ラッパワークフロー（review_command.yml / review_reply.yml）の生成をスキップします。",
                "Skips generating the CI wrapper workflows (review_command.yml / review_reply.yml)."
              ),
            ],
            [
              <DocInline key="we">--with-engines</DocInline>,
              l(
                "TS エンジンサイドカー（.ame-review/engines-ts/）を展開し npm 依存をインストールします。",
                "Expands the TS engine sidecar (.ame-review/engines-ts/) and installs npm dependencies."
              ),
            ],
            [
              <DocInline key="f">--force</DocInline>,
              l(
                "既存ファイルを上書きします。既定は「ファイルが存在すればスキップ」です。",
                "Overwrites existing files. By default, existing files are skipped."
              ),
            ],
          ]}
        />
        <DocP>
          {l(
            "生成物は以下のとおりです。CI は reusable workflow を呼ぶ薄いラッパのため、更新は --ref の差し替えのみです。",
            "The generated files are listed below. CI wrappers are thin, so upgrades are just a --ref bump."
          )}
        </DocP>
        <DocPre>
          {`.ame-review/config.json
.ame-review/review_prompt.txt
.pre-commit-config.yaml
.github/workflows/review_command.yml
.github/workflows/review_reply.yml`}
        </DocPre>
        <DocWarning>
          {l(
            "Gate 2 の静的解析は /request-review 実行時のみです。init が生成するのは上記ラッパのみで、push / pull_request 時に走る静的解析 CI は含まれません。ブランチへの push 時にも静的解析を回したい場合は、wheel 同梱の ame_ai_review_system/templates/workflow/ci.yml を .github/workflows/ci.yml として配置してください。",
            "Gate 2 static analysis runs only when /request-review is invoked. init only generates the wrappers above; no push / pull_request static-analysis CI is included. To also run static analysis on branch push, copy the bundled ame_ai_review_system/templates/workflow/ci.yml to .github/workflows/ci.yml."
          )}
        </DocWarning>
        <DocP>
          {l(
            "LLM エンジン SDK は個別に導入します（オプション）。",
            "LLM engine SDKs are installed separately (optional)."
          )}
        </DocP>
        <DocPre>
          {`pip install claude-agent-sdk       # Claude Python SDK
pip install google-antigravity     # Antigravity (Gemini)`}
        </DocPre>

        <DocH3>
          {l(
            "方式 B: ディレクトリコピー（オフライン・細かなカスタマイズ向け）",
            "Option B: directory copy (offline / fine-tuning)"
          )}
        </DocH3>
        <DocPre>
          {`cp -r .github/ /path/to/your-repo/
cp -r ame_ai_review_system/ /path/to/your-repo/`}
        </DocPre>
        <DocNote>
          {l(
            "方式 A は ame-ai-reviewer init が reusable workflow の薄いラッパを生成します。方式 B は .github/ をコピーする従来方式です。",
            "Option A generates thin reusable-workflow wrappers via ame-ai-reviewer init. Option B copies .github/ directly (legacy approach)."
          )}
        </DocNote>
      </Section>

      <Section
        title={l(
          "2. AI エージェント用スキル（review-round）の導入",
          "2. Install the AI-agent skill (review-round)"
        )}
      >
        <DocP>
          {l(
            ".claude/skills/review-round/SKILL.md にスキルを配置すると、AI エージェントが Dual-Gate レビューラウンド（Gate 1 → Gate 2）を自律的に完遂できます。",
            "Placing the skill at .claude/skills/review-round/SKILL.md lets the AI agent autonomously complete the Dual-Gate review round (Gate 1 → Gate 2)."
          )}
        </DocP>
        <DocPre>
          {`mkdir -p .claude/skills/review-round
curl -fsSL https://raw.githubusercontent.com/AME-Team/AME-AI-Review-System/v0.1.0/.claude/skills/review-round/SKILL.md \\
  -o .claude/skills/review-round/SKILL.md`}
        </DocPre>
      </Section>

      <Section
        title={l("3. GitHub App の登録と Secret 設定", "3. Register a GitHub App and set Secrets")}
      >
        <DocList
          items={[
            l(
              "レビュー用 GitHub App を作成し、対象リポジトリにインストールします。必要な権限は Contents: Read / Pull requests: Read & Write / Issues: Read & Write。",
              "Create a GitHub App for reviews and install it on the target repository. Required permissions: Contents: Read / Pull requests: Read & Write / Issues: Read & Write."
            ),
            <span key="s">
              {l("以下を Secrets に登録します: ", "Register the following Secrets: ")}
              <DocInline>AME_AI_REVIEWER_APP_ID</DocInline>
              {l("（App ID 数値）と ", " (numeric App ID) and ")}
              <DocInline>AME_AI_REVIEWER_APP_PRIVATE_KEY</DocInline>
              {l("（.pem 内容全体）。", " (full .pem content).")}
            </span>,
            l(
              "CI ワークフローは actions/create-github-app-token@v2 で都度インストールトークンを取得します。",
              "The CI workflow obtains an installation token on demand via actions/create-github-app-token@v2."
            ),
          ]}
        />
      </Section>

      <Section title={l("4. プロンプトの調整", "4. Adjust the prompt")}>
        <DocP>
          {l(
            "ame_ai_review_system/review_prompt.txt をプロジェクトの規約や観点に合わせてカスタマイズします。",
            "Customize ame_ai_review_system/review_prompt.txt to your project's conventions and review focus."
          )}
        </DocP>
      </Section>

      <Section title={l("5. レビュー依頼", "5. Request a review")}>
        <DocP>
          {l(
            "PR を作成したら、PR コメントで /request-review を入力してレビューを依頼します。",
            "After creating a PR, post /request-review in the PR comments to request a review."
          )}
        </DocP>
      </Section>

      <DocNote>
        {l(
          "pre-commit 時の AI レビューもデフォルトで有効です。git commit 時にローカルで AI レビューが走り、指摘があればコミットをブロックします。詳しくは Gate 1 のページを参照してください。",
          "The pre-commit AI review is also enabled by default: a local AI review runs on git commit and blocks it when issues are found. See the Gate 1 page for details."
        )}
      </DocNote>
    </PageShell>
  );
};

/* ------------------------------------------------------------------ */
/* Gate 1 (pre-commit)                                                 */
/* ------------------------------------------------------------------ */

const Gate1Page: React.FC<{ t: TranslationResource; locale: Locale }> = ({ t, locale }) => {
  const isJa = locale === "ja";
  const l = (ja: string, en: string): string => (isJa ? ja : en);
  return (
    <PageShell>
      <DocH1>{t.pageGate1}</DocH1>
      <DocP>
        {l(
          "Gate 1 はローカルの pre-commit フックとして動作します。git commit を実行すると、ステージされたファイルに対して静的解析と AI レビューが順に実行され、問題があればコミットをブロックします。",
          "Gate 1 runs as a local pre-commit hook. On git commit, static analysis and an AI review run against the staged files; issues block the commit."
        )}
      </DocP>

      <Section title={l("処理の流れ", "Flow")}>
        <DocList
          ordered
          items={[
            l(
              "git add でファイルをステージし、git commit を実行",
              "Stage files with git add and run git commit"
            ),
            l(
              "pre-commit が静的解析（ruff / mypy / semgrep 等）を実行。pre-commit フレームワーク内（PRE_COMMIT 環境変数あり）では静的解析を再実行せず、フック結果をそのまま利用",
              "pre-commit runs static analysis (ruff / mypy / semgrep, etc.). Inside the pre-commit framework (PRE_COMMIT is set) the static checks are not re-run; hook results are reused"
            ),
            l(
              "静的解析が全て pass した場合のみ、ローカル AI レビュー（precommit_review.py）を実行",
              "Only when all static checks pass, the local AI review (precommit_review.py) runs"
            ),
            l(
              "レビュー結果で判定: 指摘 0 件 → PASS / CRITICAL・HIGH・MIDDLE あり → BLOCK / LOW のみ → streak を +1",
              "Judgement: 0 issues → PASS / any CRITICAL・HIGH・MIDDLE → BLOCK / LOW-only → streak +1"
            ),
            l(
              "LOW のみの指摘が 2 回連続するとエスケープハッチが発動して PASS（無限ループ回避）",
              "The escape hatch PASSes after 2 consecutive LOW-only reviews (avoids infinite loops)"
            ),
            l(
              "コミット成功後、post-commit フックが streak カウンタをリセット",
              "After a successful commit, the post-commit hook resets the streak counter"
            ),
          ]}
        />
      </Section>

      <Section
        title={l("エスケープハッチ（無限ループ回避）", "Escape hatches (avoiding infinite loops)")}
      >
        <DocTable
          head={[l("条件", "Condition"), l("動作", "Behavior")]}
          rows={[
            [
              l("LOW のみの指摘が 2 回連続", "2 consecutive LOW-only reviews"),
              l("PASS（コミット許可）", "PASS (commit allowed)"),
            ],
            [
              l(
                "エンジン失敗（LLM 呼び出し失敗）が 3 回連続",
                "3 consecutive engine failures (LLM call failures)"
              ),
              l("escape（コミット許可）", "escape (commit allowed)"),
            ],
          ]}
        />
        <DocNote>
          {l(
            "PR レビュー（Gate 2）にも同様の streak 管理（2 回連続 LOW で PASS）と stale-loop 検出（強制 LGTM）が用意されています。",
            "The PR review (Gate 2) has the same streak management (PASS after 2 consecutive LOW) and stale-loop detection (forced LGTM)."
          )}
        </DocNote>
      </Section>

      <Section title={l("SKIP バイパスの防止", "Preventing SKIP bypass")}>
        <DocP>
          {l(
            "AI エージェントが SKIP=ai-precommit-review で AI レビューをすり抜けることを防ぐため、ai-skip-guard フックと skip_guard.py が検査します。ai_review_enforce_no_skip が ON（既定）のとき、Git 管理対象の config.json に基づいて強制ブロックします。",
            "The ai-skip-guard hook and skip_guard.py prevent AI agents from slipping past the AI review with SKIP=ai-precommit-review. When ai_review_enforce_no_skip is ON (default), it hard-blocks based on the tracked config.json."
          )}
        </DocP>
        <DocP>
          {l(
            "より強固にするにはネイティブ Git フックを有効化します。bash scripts/install-hooks.sh を実行すると core.hooksPath=githooks が設定され、pre-commit フレームワークの SKIP が届かないレイヤで検査します。",
            "For a stronger guarantee, enable native Git hooks. Running bash scripts/install-hooks.sh sets core.hooksPath=githooks and inspects at a layer where the pre-commit framework's SKIP never reaches."
          )}
        </DocP>
        <DocPre>{`bash scripts/install-hooks.sh`}</DocPre>
      </Section>

      <Section title={l("関連する設定キー", "Related configuration keys")}>
        <DocTable
          head={[l("キー", "Key"), l("既定", "Default"), l("説明", "Description")]}
          rows={[
            [
              <DocInline key="e">precommit_review_enabled</DocInline>,
              "true",
              l("Gate 1 の AI レビューを有効にするか", "Enable the Gate 1 AI review"),
            ],
            [
              <DocInline key="s">precommit_require_static_checks</DocInline>,
              "true",
              l(
                "静的解析がエラーの場合に AI レビューをスキップするか",
                "Skip the AI review when static checks error"
              ),
            ],
            [
              <DocInline key="a">precommit_engine</DocInline>,
              "auto",
              l(
                "Gate 1 のエンジン（auto はプロセスツリーから自動検出）",
                "Gate 1 engine (auto detects from the process tree)"
              ),
            ],
            [
              <DocInline key="m">precommit_model</DocInline>,
              "null",
              l("Gate 1 のモデル", "Gate 1 model"),
            ],
            [
              <DocInline key="t">precommit_thinking</DocInline>,
              "null",
              l(
                "Gate 1 の思考量（low / medium / high）",
                "Gate 1 thinking effort (low / medium / high)"
              ),
            ],
            [
              <DocInline key="b">precommit_review_budget_usd</DocInline>,
              "null",
              l(
                "Gate 1 の予算上限（未設定時は review_budget_usd）",
                "Gate 1 budget cap (falls back to review_budget_usd)"
              ),
            ],
          ]}
        />
      </Section>

      <DocNote>
        {l(
          "既存クローンで pre-commit install 済みの場合は、post-commit フック（streak リセット）を含めて再実行してください: pre-commit install -t pre-commit -t post-commit",
          "If you already ran pre-commit install in an existing clone, re-run it including the post-commit hook (streak reset): pre-commit install -t pre-commit -t post-commit"
        )}
      </DocNote>
    </PageShell>
  );
};

/* ------------------------------------------------------------------ */
/* Gate 2 (PR review)                                                  */
/* ------------------------------------------------------------------ */

const Gate2Page: React.FC<{ t: TranslationResource; locale: Locale }> = ({ t, locale }) => {
  const isJa = locale === "ja";
  const l = (ja: string, en: string): string => (isJa ? ja : en);
  return (
    <PageShell>
      <DocH1>{t.pageGate2}</DocH1>
      <DocP>
        {l(
          "Gate 2 は CI/CD の Pull Request 上で動作します。PR コメントで /request-review を投稿すると、Circuit Breaker 静的解析を経て AI レビューが実行され、インラインコメントで指摘が投稿されます。",
          "Gate 2 runs on Pull Requests in CI/CD. Posting /request-review triggers the AI review after the Circuit Breaker static checks, and findings are posted as inline comments."
        )}
      </DocP>

      <Section title={l("レビュー依頼のコマンド", "Review request command")}>
        <DocTable
          head={[l("コマンド", "Command"), l("説明", "Description")]}
          rows={[
            [
              <DocInline key="rr">/request-review</DocInline>,
              l("PR コメントでレビューを依頼します", "Requests a review from the PR comments"),
            ],
            [
              <DocInline key="r">/review</DocInline>,
              l("同一コマンドのエイリアス", "Alias for the same command"),
            ],
          ]}
        />
      </Section>

      <Section title={l("処理の流れ", "Flow")}>
        <DocList
          ordered
          items={[
            l(
              "PR を作成し、PR コメントで /request-review を投稿",
              "Create a PR and post /request-review in the PR comments"
            ),
            l(
              "review_command.yml ワークフローが起動し、Circuit Breaker 静的解析（static_precheck.py）を実行",
              "The review_command.yml workflow starts and runs the Circuit Breaker static checks (static_precheck.py)"
            ),
            l(
              "静的解析でエラーが 0 件の場合のみ AI レビューを実行。エラーがあれば「Skipping AI review」としてスキップ（トークン消費を抑制）",
              "AI review runs only when static checks report 0 errors; otherwise it skips with “Skipping AI review” to save tokens"
            ),
            l(
              "同一 HEAD SHA は再レビューせずスキップ（reviewed-sha マーカーで重複を防止）。PR ごとのレビュー回数は最大 10 回",
              "The same HEAD SHA is not re-reviewed (deduplicated via the reviewed-sha marker). Max 10 review rounds per PR"
            ),
            l(
              "指摘は PR のインラインコメントとして投稿。重大度は CRITICAL / HIGH / MIDDLE / LOW の 4 段階",
              "Findings are posted as PR inline comments with severity CRITICAL / HIGH / MIDDLE / LOW"
            ),
            l(
              "開発者はインラインスレッドに @ame-ai-reviewer[bot] で返信。AI が最新コードを再評価して返答",
              "The developer replies with @ame-ai-reviewer[bot] in the thread; the AI re-evaluates the latest code and replies"
            ),
            l(
              "LGTM ✅ を受け取ったスレッドを Resolve し、全て解決したら再度 /request-review で再レビュー",
              "Resolve threads that received LGTM ✅; once all are resolved, re-request via /request-review"
            ),
          ]}
        />
      </Section>

      <Section title={l("返信・Resolve の仕組み", "Reply and Resolve mechanism")}>
        <DocP>
          {l(
            "返信判定は reply.py が担当します。トリガーとなったスレッド 1 件だけを対象に、実際の diff を読んで「LGTM」か「追加指摘」かを判断します。/ で始まるコメント（コマンド）や PR 本文コメントでは発火しません。",
            "reply.py handles reply judgement. It targets only the triggering thread, reads the actual diff, and decides between LGTM and additional findings. It does not fire for command comments (starting with /) or PR body comments."
          )}
        </DocP>
        <DocTable
          head={[l("操作", "Action"), l("API / 方式", "API / Method")]}
          rows={[
            [
              l("スレッド返信", "Reply to a thread"),
              <DocInline key="a">
                POST /repos/{`{owner}/{repo}`}/pulls/{`{pr}`}/comments/{`{id}`}/replies
              </DocInline>,
            ],
            [
              l("スレッド Resolve", "Resolve a thread"),
              <DocInline key="b">GraphQL resolveReviewThread (input: {"{threadId}"})</DocInline>,
            ],
          ]}
        />
        <DocNote>
          {l(
            "stale-loop 検出（Jaccard 類似度 ≥ 0.80、または連続 non-LGTM 3 回以上）で膠着を検出した場合は強制 LGTM を投稿し、無限ループを防ぎます。",
            "Stale-loop detection (Jaccard similarity ≥ 0.80, or 3+ consecutive non-LGTM replies) posts a forced LGTM to break a stalemate."
          )}
        </DocNote>
      </Section>

      <Section title={l("関連する設定キー", "Related configuration keys")}>
        <DocTable
          head={[l("キー", "Key"), l("既定", "Default"), l("説明", "Description")]}
          rows={[
            [
              <DocInline key="cb">pr_review_require_static_checks</DocInline>,
              "true",
              l(
                "PR レビューの Circuit Breaker を有効にするか",
                "Enable the Circuit Breaker for PR reviews"
              ),
            ],
            [
              <DocInline key="rr">review_model</DocInline>,
              "null",
              l(
                "レビュー時のモデル（未設定時は engine の既定）",
                "Review-time model (falls back to the engine default)"
              ),
            ],
            [
              <DocInline key="rt">review_thinking</DocInline>,
              "low",
              l("レビュー時の思考量", "Review-time thinking effort"),
            ],
            [
              <DocInline key="rb">review_budget_usd</DocInline>,
              "2.0",
              l("レビュー時の予算上限（USD）", "Review-time budget cap (USD)"),
            ],
            [
              <DocInline key="pl">reply_model</DocInline>,
              "haiku",
              l("返信判定時のモデル", "Reply-judgement model"),
            ],
            [
              <DocInline key="pt">reply_thinking</DocInline>,
              "low",
              l("返信判定時の思考量", "Reply-judgement thinking effort"),
            ],
            [
              <DocInline key="pb">reply_budget_usd</DocInline>,
              "0.2",
              l("返信判定時の予算上限（USD）", "Reply-judgement budget cap (USD)"),
            ],
          ]}
        />
      </Section>
    </PageShell>
  );
};

/* ------------------------------------------------------------------ */
/* Demo                                                                */
/* ------------------------------------------------------------------ */

const DemoPage: React.FC<{ t: TranslationResource; locale: Locale }> = ({ t, locale }) => {
  return (
    <PageShell>
      <DocH1>{t.pageDemo}</DocH1>
      <DocP>{t.demoDesc}</DocP>
      <Simulator t={t} locale={locale} />
      <DocNote>
        {locale === "ja"
          ? "このデモはブラウザ上での疑似体験です。実際の環境では precommit_review.py がローカルで AI レビューを実行します。"
          : "This demo is a browser-based simulation. In a real environment, precommit_review.py runs the local AI review."}
      </DocNote>
    </PageShell>
  );
};

/* ------------------------------------------------------------------ */
/* config.json                                                         */
/* ------------------------------------------------------------------ */

const ConfigJsonPage: React.FC<{ t: TranslationResource; locale: Locale }> = ({ t, locale }) => {
  const isJa = locale === "ja";
  const l = (ja: string, en: string): string => (isJa ? ja : en);
  return (
    <PageShell>
      <DocH1>{t.pageConfigJson}</DocH1>
      <DocP>
        {l(
          "config.json は ame_ai_review_system/config.json（または .ame-review/config.json）に配置します。既定値 → config.json → config.user.json の順にマージされ、後者が優先されます。",
          "config.json lives at ame_ai_review_system/config.json (or .ame-review/config.json). Settings are merged in the order defaults → config.json → config.user.json, with the later taking priority."
        )}
      </DocP>

      <Section title={l("設定キー一覧", "Configuration keys")}>
        <DocTable
          head={[l("キー", "Key"), l("既定", "Default"), l("説明", "Description")]}
          rows={[
            [
              "precommit_review_enabled",
              "true",
              l(
                "Gate 1（pre-commit）の AI レビューを有効にするか",
                "Enable the Gate 1 (pre-commit) AI review"
              ),
            ],
            [
              "precommit_require_static_checks",
              "true",
              l(
                "Gate 1 で静的解析がエラーの場合に AI レビューをスキップするか",
                "Skip the Gate 1 AI review when static checks error"
              ),
            ],
            [
              "pr_review_require_static_checks",
              "true",
              l(
                "Gate 2（PR）の Circuit Breaker（静的解析失敗時に AI レビューをスキップ）を有効にするか",
                "Enable the Gate 2 (PR) Circuit Breaker that skips AI review on static check errors"
              ),
            ],
            [
              "ai_review_enforce_no_skip",
              "true",
              l(
                "SKIP=ai-precommit-review バイパスを強制ブロックするか",
                "Hard-block SKIP=ai-precommit-review bypasses"
              ),
            ],
            [
              "review_include_package_dir",
              "false",
              l(
                "vendored パッケージ配下もレビュー対象に含めるか",
                "Include vendored package directories in the review scope"
              ),
            ],
            [
              "include_test_target_diff",
              "false",
              l(
                "テストのみのステージ時に、テスト対象モジュールの実装コンテキストを diff に含めるか",
                "Include the implementation context of tested modules when only tests are staged"
              ),
            ],
            [
              "precommit_engine",
              "auto",
              l(
                "Gate 1 のエンジン（auto はプロセスツリーから自動検出）",
                "Gate 1 engine (auto detects from the process tree)"
              ),
            ],
            ["precommit_model", "null", l("Gate 1 のモデル", "Gate 1 model")],
            [
              "precommit_thinking",
              "null",
              l(
                "Gate 1 の思考量（low / medium / high）",
                "Gate 1 thinking effort (low / medium / high)"
              ),
            ],
            [
              "precommit_review_budget_usd",
              "null",
              l(
                "Gate 1 の予算上限（未設定時は review_budget_usd）",
                "Gate 1 budget cap (falls back to review_budget_usd)"
              ),
            ],
            [
              "show_engine_info_gate1",
              "true",
              l("Gate 1 のエンジン情報を表示するか", "Show Gate 1 engine info"),
            ],
            [
              "show_engine_info_gate2",
              "true",
              l("Gate 2 のエンジン情報を表示するか", "Show Gate 2 engine info"),
            ],
            [
              "review_repair_model",
              "null",
              l(
                "JSON パース失敗時の LLM 修復モデル（未設定時は review_model）",
                "LLM repair model for JSON parse failures (falls back to review_model)"
              ),
            ],
            [
              "review_repair_attempts",
              "3",
              l(
                "JSON 修復の最大試行回数（0 で無効化）",
                "Max repair attempts for JSON parsing (0 disables)"
              ),
            ],
            [
              "stale_jaccard_threshold",
              "0.80",
              l(
                "stale-loop 判定の Jaccard 類似度閾値",
                "Jaccard similarity threshold for stale-loop detection"
              ),
            ],
            [
              "engine",
              "claude",
              l(
                "既定エンジン（claude / opencode / antigravity）",
                "Default engine (claude / opencode / antigravity)"
              ),
            ],
            [
              "model",
              "null",
              l("既定モデル（claude 時は sonnet が既定）", "Default model (sonnet for claude)"),
            ],
            ["review_model", "null", l("レビュー時のモデル", "Review-time model")],
            ["reply_model", "haiku", l("返信判定時のモデル", "Reply-judgement model")],
            ["thinking", "low", l("既定の思考量", "Default thinking effort")],
            ["review_thinking", "low", l("レビュー時の思考量", "Review-time thinking effort")],
            ["reply_thinking", "low", l("返信判定時の思考量", "Reply-judgement thinking effort")],
            [
              "review_budget_usd",
              "2.0",
              l("レビュー時の予算上限（USD）", "Review-time budget cap (USD)"),
            ],
            [
              "reply_budget_usd",
              "0.2",
              l("返信判定時の予算上限（USD）", "Reply-judgement budget cap (USD)"),
            ],
            ["max_diff_lines", "4000", l("diff 切り捨ての上限行数", "Diff truncation line limit")],
            [
              "diff_truncation_strategy",
              "priority",
              l(
                "切り捨て戦略（priority / front / head_tail）",
                "Truncation strategy (priority / front / head_tail)"
              ),
            ],
            [
              "diff_truncation_context_lines",
              "800",
              l(
                "切り捨て時のコンテキスト最低保証行数",
                "Minimum guaranteed context lines when truncating"
              ),
            ],
          ]}
        />
        <DocNote>
          {l(
            "任意キーとして tsconfig_path（TS 静的解析の tsconfig 指定）と sdk_lang（エンジン SDK 言語）も参照できます。",
            "Optional keys tsconfig_path (tsconfig for TS static checks) and sdk_lang (engine SDK language) are also referenced."
          )}
        </DocNote>
      </Section>

      <Section
        title={l(
          "ユーザー固有設定（config.user.json）",
          "User-specific settings (config.user.json)"
        )}
      >
        <DocP>
          {l(
            "config.user.json（Git 管理対象外）で環境依存の設定を上書きできます。config.json より優先されます。例えば Gate 1 のエンジンだけ変更する場合は次のように記述します。",
            "config.user.json (not tracked by Git) overrides environment-specific settings and takes priority over config.json. For example, to change only the Gate 1 engine:"
          )}
        </DocP>
        <DocPre>{`{ "precommit_engine": "claude", "precommit_model": "sonnet" }`}</DocPre>
      </Section>

      <Section title={l("設定の優先順位", "Priority order")}>
        <DocList
          ordered
          items={[
            l(
              "組み込みの既定値（review_config.py の _DEFAULTS）",
              "Built-in defaults (_DEFAULTS in review_config.py)"
            ),
            l(
              "config.json（環境変数 AME_REVIEW_CONFIG でパスを上書き可能）",
              "config.json (path overridable via AME_REVIEW_CONFIG)"
            ),
            l(
              "config.user.json（環境変数 AME_REVIEW_USER_CONFIG でパスを上書き可能）",
              "config.user.json (path overridable via AME_REVIEW_USER_CONFIG)"
            ),
            l(
              "環境変数（PRECOMMIT_REVIEW_* / REVIEW_* 等）",
              "Environment variables (PRECOMMIT_REVIEW_* / REVIEW_* etc.)"
            ),
          ]}
        />
      </Section>
    </PageShell>
  );
};

/* ------------------------------------------------------------------ */
/* Environment variables                                               */
/* ------------------------------------------------------------------ */

const EnvVarsPage: React.FC<{ t: TranslationResource; locale: Locale }> = ({ t, locale }) => {
  const isJa = locale === "ja";
  const l = (ja: string, en: string): string => (isJa ? ja : en);
  return (
    <PageShell>
      <DocH1>{t.pageEnvVars}</DocH1>
      <DocP>
        {l(
          "設定は環境変数でも上書きできます。設定ファイルより環境変数が優先されます。",
          "Settings can also be overridden by environment variables, which take priority over config files."
        )}
      </DocP>

      <Section title={l("パス・実行環境", "Paths & execution environment")}>
        <DocTable
          head={[l("環境変数", "Variable"), l("説明", "Description")]}
          rows={[
            [
              "AME_REVIEW_CONFIG",
              l("config.json のパスを上書き", "Overrides the config.json path"),
            ],
            [
              "AME_REVIEW_USER_CONFIG",
              l("config.user.json のパスを上書き", "Overrides the config.user.json path"),
            ],
            [
              "AME_REVIEW_PROJECT_ROOT",
              l("プロジェクトルートを上書き", "Overrides the project root"),
            ],
            [
              "REVIEWER_NAME",
              l("レビュアー名（既定 ame-ai-reviewer）", "Reviewer name (default ame-ai-reviewer)"),
            ],
            ["REVIEWER_TOKEN", l("レビュー用トークン", "Review token")],
            ["GITHUB_PAT_TOKEN", l("GitHub アクセストークン", "GitHub access token")],
            [
              "GITHUB_REPOSITORY / GITHUB_API_URL / GITHUB_GRAPHQL_URL",
              l("GitHub REST/GraphQL のリポジトリ・URL", "GitHub REST/GraphQL repository and URLs"),
            ],
            ["BASE_REF", l("ベースブランチ（既定 main）", "Base branch (default main)")],
            [
              "PR_TITLE / PR_BODY / GITHUB_ENV",
              l("checkout コマンドの出力先", "checkout command output targets"),
            ],
          ]}
        />
      </Section>

      <Section title={l("エンジン（Gate 2 / 返信判定）", "Engines (Gate 2 / reply judgement)")}>
        <DocTable
          head={[l("環境変数", "Variable"), l("説明", "Description")]}
          rows={[
            [
              "REVIEW_ENGINE",
              l(
                "エンジン（claude / opencode / antigravity）",
                "Engine (claude / opencode / antigravity)"
              ),
            ],
            [
              "REVIEW_MODEL / REPLY_MODEL",
              l("レビュー時・返信判定時のモデル", "Review-time and reply-judgement models"),
            ],
            [
              "REVIEW_THINKING / REPLY_THINKING",
              l(
                "レビュー時・返信判定時の思考量（low / medium / high）",
                "Review-time and reply-judgement thinking effort (low / medium / high)"
              ),
            ],
            [
              "REVIEW_BUDGET_USD / REPLY_BUDGET_USD",
              l(
                "レビュー時・返信判定時の予算上限（USD）",
                "Review-time and reply-judgement budget caps (USD)"
              ),
            ],
            [
              "REVIEW_SDK_LANG / CLAUDE_SDK_LANG",
              l(
                "エンジン SDK の言語（python / typescript）",
                "Engine SDK language (python / typescript)"
              ),
            ],
            [
              "REVIEW_TIMEOUT_SECONDS",
              l("エンジン実行のタイムアウト（既定 600）", "Engine execution timeout (default 600)"),
            ],
            [
              "AME_ENGINE_SHOW_INFO",
              l("エンジン情報バナーの表示制御（1 / 0）", "Engine info banner control (1 / 0)"),
            ],
            ["CLAUDE_MODEL", l("claude エンジンのモデル", "Claude engine model")],
          ]}
        />
      </Section>

      <Section title={l("エンジン（Gate 1 / pre-commit）", "Engines (Gate 1 / pre-commit)")}>
        <DocTable
          head={[l("環境変数", "Variable"), l("説明", "Description")]}
          rows={[
            ["PRECOMMIT_REVIEW_ENGINE", l("Gate 1 のエンジン", "Gate 1 engine")],
            ["PRECOMMIT_REVIEW_MODEL", l("Gate 1 のモデル", "Gate 1 model")],
            ["PRECOMMIT_REVIEW_THINKING", l("Gate 1 の思考量", "Gate 1 thinking effort")],
            ["PRECOMMIT_REVIEW_BUDGET_USD", l("Gate 1 の予算上限", "Gate 1 budget cap")],
          ]}
        />
      </Section>

      <Section title={l("init / 認証 / フロント", "init / auth / frontend")}>
        <DocTable
          head={[l("環境変数", "Variable"), l("説明", "Description")]}
          rows={[
            [
              "AME_INIT_PYTHON",
              l(
                "init を language: system 方式に切り替える（オフライン向け）",
                "Switches init to language: system mode (offline)"
              ),
            ],
            [
              "CLAUDE_CONFIG_B64 / CLAUDE_CREDENTIALS_B64",
              l("Claude の認証情報（Base64）", "Claude credentials (Base64)"),
            ],
            [
              "OPENCODE_AUTH_B64 / ANTIGRAVITY_OAUTH_B64 / GEMINI_OAUTH_B64",
              l(
                "OpenCode / Antigravity / Gemini の認証情報",
                "OpenCode / Antigravity / Gemini credentials"
              ),
            ],
            [
              "GEMINI_API_KEY / GOOGLE_API_KEY",
              l("Antigravity の API キー", "Antigravity API key"),
            ],
            [
              "OPENCODE_SERVER_USERNAME / OPENCODE_SERVER_PASSWORD",
              l("OpenCode サーバーの Basic 認証", "OpenCode server basic auth"),
            ],
            [
              "VITE_GITHUB_URL",
              l("ランディングページの GitHub リンク先", "Landing page GitHub link target"),
            ],
          ]}
        />
      </Section>
    </PageShell>
  );
};

/* ------------------------------------------------------------------ */
/* Config examples                                                     */
/* ------------------------------------------------------------------ */

const ConfigExamplesPage: React.FC<{ t: TranslationResource; locale: Locale }> = ({
  t,
  locale,
}) => {
  const isJa = locale === "ja";
  const l = (ja: string, en: string): string => (isJa ? ja : en);
  return (
    <PageShell>
      <DocH1>{t.pageConfigExamples}</DocH1>
      <DocP>{t.configDesc}</DocP>

      <Section title={l("config.json の例", "config.json example")}>
        <DocPre>
          {`{
  "precommit_review_enabled": true,
  "precommit_require_static_checks": true,
  "pr_review_require_static_checks": true,
  "ai_review_enforce_no_skip": true,
  "review_include_package_dir": false,
  "precommit_engine": "auto",
  "engine": "claude",
  "model": null,
  "review_model": null,
  "reply_model": "haiku",
  "thinking": "low",
  "review_thinking": "low",
  "reply_thinking": "low",
  "show_engine_info_gate1": true,
  "show_engine_info_gate2": true,
  "review_budget_usd": 2.0,
  "reply_budget_usd": 0.2
}`}
        </DocPre>
      </Section>

      <Section title={l("チュートリアル用コード", "Tutorial code")}>
        <ConfigTabs t={t} locale={locale} />
      </Section>
    </PageShell>
  );
};

/* ------------------------------------------------------------------ */
/* Architecture                                                        */
/* ------------------------------------------------------------------ */

const ArchitecturePage: React.FC<{ t: TranslationResource; locale: Locale }> = ({ t, locale }) => {
  const isJa = locale === "ja";
  const l = (ja: string, en: string): string => (isJa ? ja : en);
  return (
    <PageShell>
      <DocH1>{t.pageArchitecture}</DocH1>
      <DocP>
        {l(
          "本システムは CLI（ame-ai-reviewer）と GitHub Actions ワークフローで構成されます。CLI は標準ライブラリのみで動作し、LLM エンジンは SDK アダプタ層（engine.py）を経由して Claude Code / OpenCode / Antigravity を切り替えます。",
          "This system consists of a CLI (ame-ai-reviewer) and GitHub Actions workflows. The CLI runs on the standard library only, and LLM engines are switched via the SDK adapter layer (engine.py) among Claude Code, OpenCode, and Antigravity."
        )}
      </DocP>

      <Section title={l("二重ゲートの処理フロー", "Dual-gate processing flow")}>
        <DualGateFlowDiagram locale={locale} />
        <PipelineDiagram t={t} locale={locale} />
      </Section>

      <Section title={l("モジュール構成", "Module layout")}>
        <DocTable
          head={[l("モジュール", "Module"), l("役割", "Role")]}
          rows={[
            [
              <DocInline key="m">main.py</DocInline>,
              l(
                "CLI エントリポイント（init / review / checkout / setup サブコマンド）",
                "CLI entry point (init / review / checkout / setup subcommands)"
              ),
            ],
            [
              <DocInline key="i">init_cmd.py</DocInline>,
              l(
                "ame-ai-reviewer init 本体（プリセット選択・workflow 生成）",
                "ame-ai-reviewer init implementation (presets, workflow generation)"
              ),
            ],
            [
              <DocInline key="r">reply.py</DocInline>,
              l(
                "返信プロンプト生成・スレッド解析・stale-loop 検出",
                "Reply prompt building, thread analysis, stale-loop detection"
              ),
            ],
            [
              <DocInline key="g">github_client.py</DocInline>,
              l(
                "GitHub REST/GraphQL API 共通クライアント（Resolve 等）",
                "Shared GitHub REST/GraphQL client (incl. Resolve)"
              ),
            ],
            [
              <DocInline key="e">engine.py</DocInline>,
              l(
                "LLM エンジンアダプタ（claude / opencode / antigravity、role 別設定）",
                "LLM engine adapter (claude / opencode / antigravity, per-role settings)"
              ),
            ],
            [
              <DocInline key="p">payload.py</DocInline>,
              l(
                "モデル出力 → GitHub API ペイロード変換",
                "Model output → GitHub API payload conversion"
              ),
            ],
            [
              <DocInline key="c">review_config.py</DocInline>,
              l("設定読み込み・コマンド判定ヘルパ", "Config loading and command judgement helper"),
            ],
            [
              <DocInline key="s">static_precheck.py</DocInline>,
              l(
                "PR レビュー前段の静的解析 pre-check（Circuit Breaker）",
                "Static-analysis pre-check before PR review (Circuit Breaker)"
              ),
            ],
            [
              <DocInline key="d">diff_utils.py / diff_base.py / diff_truncate.py</DocInline>,
              l(
                "diff の圧縮・比較元解決・戦略的切り捨て",
                "Diff compression, base resolution, and strategic truncation"
              ),
            ],
            [
              <DocInline key="ps">
                pr_streak.py / precommit_review.py / precommit_state.py
              </DocInline>,
              l(
                "streak 管理・pre-commit AI レビュー本体・状態管理",
                "Streak management, pre-commit AI review, state management"
              ),
            ],
            [
              <DocInline key="pd">stale_detect.py / skip_guard.py / paths.py</DocInline>,
              l(
                "stale-loop 共通実装・SKIP バイパス防止・パス解決",
                "Stale-loop implementation, SKIP-bypass guard, path resolution"
              ),
            ],
          ]}
        />
      </Section>

      <Section title={l("動作の流れ（Gate 2）", "Execution flow (Gate 2)")}>
        <DocList
          ordered
          items={[
            l(
              "PR コメント /request-review → review_command.yml 起動",
              "/request-review in PR comments → review_command.yml starts"
            ),
            l(
              "main review <pr> を実行（REVIEWER_TOKEN / REVIEWER_NAME は環境変数）",
              "Runs main review <pr> (REVIEWER_TOKEN / REVIEWER_NAME come from env)"
            ),
            l(
              "static_precheck.py で Circuit Breaker 静的解析",
              "static_precheck.py runs the Circuit Breaker static checks"
            ),
            l(
              "engine.py（--role review）で LLM を呼び出し",
              "Calls the LLM via engine.py (--role review)"
            ),
            l(
              "payload.py が指摘をインラインコメントのペイロードに変換し投稿",
              "payload.py converts findings into inline-comment payloads and posts them"
            ),
            l(
              "開発者の返信 → reply.py（--role reply）が LGTM / 追加指摘を判定",
              "Developer reply → reply.py (--role reply) judges LGTM or additional findings"
            ),
          ]}
        />
      </Section>
    </PageShell>
  );
};

/* ------------------------------------------------------------------ */
/* Engines                                                             */
/* ------------------------------------------------------------------ */

const EnginesPage: React.FC<{ t: TranslationResource; locale: Locale }> = ({ t, locale }) => {
  const isJa = locale === "ja";
  const l = (ja: string, en: string): string => (isJa ? ja : en);
  return (
    <PageShell>
      <DocH1>{t.pageEngines}</DocH1>
      <DocP>{t.enginesDesc}</DocP>
      <EngineComparisonSection t={t} />

      <Section title={l("エンジン / SDK 対応表", "Engine / SDK mapping")}>
        <DocTable
          head={[
            l("エンジン", "Engine"),
            l("SDK / 実装", "SDK / Implementation"),
            l("言語", "Language"),
            l("備考", "Notes"),
          ]}
          rows={[
            [
              <DocInline key="c">claude</DocInline>,
              <DocInline key="cs">claude-agent-sdk</DocInline>,
              "Python",
              l(
                "ClaudeAgentOptions (model / effort / max_budget_usd)。既定モデルは sonnet",
                "ClaudeAgentOptions (model / effort / max_budget_usd). Default model: sonnet"
              ),
            ],
            [
              <DocInline key="ct">claude</DocInline>,
              <DocInline key="ts">engines/ts/claude.mjs</DocInline>,
              "TypeScript",
              l("TS サイドカーとして実行", "Runs as a TS sidecar"),
            ],
            [
              <DocInline key="o">opencode</DocInline>,
              <DocInline key="os">engines/ts/opencode.mjs</DocInline>,
              "TypeScript",
              l(
                "opencode serve が必要。model は provider/model 形式（未指定時はサーバー既定）",
                "Requires opencode serve. Model must be provider/model; defaults to the server default"
              ),
            ],
            [
              <DocInline key="a">antigravity</DocInline>,
              <DocInline key="as">google-antigravity</DocInline>,
              "Python",
              l(
                "GeminiModelOptions (thinking_level)。model 必須",
                "GeminiModelOptions (thinking_level). Model is required"
              ),
            ],
          ]}
        />
      </Section>

      <Section
        title={l("モデル・思考量・予算の解決順", "Resolution order for model / thinking / budget")}
      >
        <DocP>
          {l(
            "エンジンは REVIEW_ENGINE 環境変数 → config の engine の順に解決します。モデル・思考量・予算はロール（review / reply）別に設定できます。",
            "The engine resolves via REVIEW_ENGINE env → config engine. Model, thinking, and budget are configurable per role (review / reply)."
          )}
        </DocP>
        <DocTable
          head={[l("項目", "Item"), l("解決順", "Resolution order")]}
          rows={[
            [
              l("モデル", "Model"),
              l(
                "環境変数（REVIEW_MODEL / REPLY_MODEL）→ ユーザー設定のロールキー → config の model → 既定",
                "Env (REVIEW_MODEL / REPLY_MODEL) → user role key → config model → default"
              ),
            ],
            [
              l("思考量", "Thinking"),
              l(
                "環境変数（REVIEW_THINKING / REPLY_THINKING）→ ユーザー設定 → config の thinking",
                "Env (REVIEW_THINKING / REPLY_THINKING) → user setting → config thinking"
              ),
            ],
            [
              l("予算", "Budget"),
              l(
                "環境変数（REVIEW_BUDGET_USD / REPLY_BUDGET_USD）→ config の review_budget_usd / reply_budget_usd",
                "Env (REVIEW_BUDGET_USD / REPLY_BUDGET_USD) → config review_budget_usd / reply_budget_usd"
              ),
            ],
          ]}
        />
      </Section>

      <DocNote>
        {l(
          "GitHub Actions 上の既定エンジンは opencode です（CI ワークフローが config の claude 既定を上書きします）。",
          "The default engine on GitHub Actions is opencode (the CI workflow overrides the claude default in config)."
        )}
      </DocNote>
    </PageShell>
  );
};

/* ------------------------------------------------------------------ */
/* Troubleshooting                                                     */
/* ------------------------------------------------------------------ */

const TroubleshootingPage: React.FC<{ t: TranslationResource; locale: Locale }> = ({
  t,
  locale,
}) => {
  const isJa = locale === "ja";
  const l = (ja: string, en: string): string => (isJa ? ja : en);
  return (
    <PageShell>
      <DocH1>{t.pageTroubleshooting}</DocH1>
      <DocP>
        {l(
          "よくある問題と対処法をまとめています。詳細は同梱ドキュメント ame_ai_review_system/docs/troubleshooting.md を参照してください。",
          "Common problems and solutions. See the bundled ame_ai_review_system/docs/troubleshooting.md for details."
        )}
      </DocP>

      <DocTable
        head={[l("症状", "Symptom"), l("原因 / 対処", "Cause / Fix")]}
        rows={[
          [
            l("AI の返信が無限ループする", "AI replies loop infinitely"),
            l(
              "review_reply.yml の if 条件に全レビュアーの bot login を != で除外してください。stale-loop 検出（Jaccard ≥ 0.80 / 連続 non-LGTM 3 回）が強制 LGTM を発行します",
              "Exclude every reviewer bot login with != in review_reply.yml's if condition. Stale-loop detection (Jaccard ≥ 0.80 / 3 consecutive non-LGTM) posts a forced LGTM"
            ),
          ],
          [
            l("LLM エンジンの SDK / サーバ接続エラー", "LLM engine SDK / server connection errors"),
            l(
              "claude-agent-sdk のインストール、opencode serve の起動、認証情報（CLAUDE_CONFIG_B64 等）を確認してください",
              "Check claude-agent-sdk installation, opencode serve startup, and credentials (CLAUDE_CONFIG_B64, etc.)"
            ),
          ],
          [
            l("レビューが実行されない（スキップ）", "Reviews are skipped"),
            l(
              "/request-review 未入力、同一 HEAD SHA の重複、GitHub App の認証無効、レビュー回数上限（既定 10 回）を確認してください",
              "Check for a missing /request-review, duplicate HEAD SHA, invalid GitHub App auth, or the review round limit (default 10)"
            ),
          ],
          [
            l(
              "/request-review で「Skipping AI review」",
              "“Skipping AI review” from /request-review"
            ),
            l(
              "Circuit Breaker が発動しています。ruff / mypy / semgrep 等の静的解析エラーを修正してください",
              "The Circuit Breaker fired. Fix the static-analysis errors (ruff / mypy / semgrep, etc.)"
            ),
          ],
          [
            l(
              "pre-commit 静的解析エラーでコミット不可",
              "Commit blocked by pre-commit static errors"
            ),
            l(
              "指摘を修正してください。SKIP によるバイパスは ai-skip-guard がブロックします",
              "Fix the findings. The ai-skip-guard blocks SKIP bypasses"
            ),
          ],
          [
            l("streak カウンタがリセットされない", "Streak counter is not reset"),
            l(
              "post-commit フックを再インストールしてください（pre-commit install -t pre-commit -t post-commit）",
              "Reinstall the post-commit hook (pre-commit install -t pre-commit -t post-commit)"
            ),
          ],
          [
            l("config.user.json が反映されない", "config.user.json is not applied"),
            l(
              "JSON 構文エラー、配置場所（.ame-review/config.user.json）、環境変数（AME_REVIEW_USER_CONFIG）による上書きを確認してください",
              "Check JSON syntax, the location (.ame-review/config.user.json), and overrides via AME_REVIEW_USER_CONFIG"
            ),
          ],
          [
            l("vendored パッケージを誤指摘する", "Vendored packages are wrongly flagged"),
            l(
              "review_include_package_dir（既定 false）で除外されています。参照時は「vendored・レビュー対象外」の注記がプロンプトへ自動追記されます",
              "Excluded by review_include_package_dir (default false). A “vendored / out of scope” note is auto-appended to the prompt when referenced"
            ),
          ],
          [
            l(
              ".ame-review/engines-ts/ の手修正が消える",
              "Manual edits to .ame-review/engines-ts/ disappear"
            ),
            l(
              "engines-ts は毎回パッケージ側から再展開されます。パッケージ側（ame_ai_review_system/engines/ts/）を修正してください",
              "engines-ts is re-expanded from the package on every run. Edit the package side (ame_ai_review_system/engines/ts/) instead"
            ),
          ],
        ]}
      />
    </PageShell>
  );
};

/* ------------------------------------------------------------------ */
/* Dispatcher                                                          */
/* ------------------------------------------------------------------ */

export interface DocPageProps {
  t: TranslationResource;
  locale: Locale;
  fontStyle: FontStyle;
  onNavigate: (id: DocPageId) => void;
}

export const DocPage: React.FC<DocPageProps & { id: DocPageId }> = ({
  id,
  t,
  locale,
  fontStyle,
  onNavigate,
}) => {
  switch (id) {
    case "overview":
      return <OverviewPage t={t} locale={locale} fontStyle={fontStyle} onNavigate={onNavigate} />;
    case "features":
      return <FeaturesPage t={t} locale={locale} onNavigate={onNavigate} />;
    case "static-analysis":
      return <StaticAnalysisPage t={t} locale={locale} />;
    case "quickstart":
      return <QuickStartPage t={t} locale={locale} />;
    case "gate1":
      return <Gate1Page t={t} locale={locale} />;
    case "gate2":
      return <Gate2Page t={t} locale={locale} />;
    case "demo":
      return <DemoPage t={t} locale={locale} />;
    case "config-json":
      return <ConfigJsonPage t={t} locale={locale} />;
    case "env-vars":
      return <EnvVarsPage t={t} locale={locale} />;
    case "config-examples":
      return <ConfigExamplesPage t={t} locale={locale} />;
    case "architecture":
      return <ArchitecturePage t={t} locale={locale} />;
    case "engines":
      return <EnginesPage t={t} locale={locale} />;
    case "troubleshooting":
      return <TroubleshootingPage t={t} locale={locale} />;
    default:
      return <OverviewPage t={t} locale={locale} fontStyle={fontStyle} onNavigate={onNavigate} />;
  }
};
