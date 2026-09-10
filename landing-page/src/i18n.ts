import { type Locale } from "./assets/headerImage";

export type { Locale };

export interface TranslationResource {
  title: string;
  githubRepo: string;
  badgeVersion: string;
  heroTitle1: string;
  heroTitleAccent: string;
  heroTitle2: string;
  heroDesc: string;
  tryDemoBtn: string;
  viewConfigBtn: string;
  secFeaturesTitle: string;
  secFeaturesDesc: string;
  featureDiffTitle: string;
  featureDiffDesc: string;
  featureCbTitle: string;
  featureCbDesc: string;
  featureGateTitle: string;
  featureGateDesc: string;
  featureAgentTitle: string;
  featureAgentDesc: string;
  featureLoopTitle: string;
  featureLoopDesc: string;
  staticAnalysisTitle: string;
  staticAnalysisDesc: string;
  staticAnalysisStatCategories: string;
  staticAnalysisStatTools: string;
  staticAnalysisConfigLabel: string;
  staticAnalysisPortabilityNote: string;
  enginesTitle: string;
  enginesDesc: string;
  engineClaudeTitle: string;
  engineClaudeDesc: string;
  engineOpencodeTitle: string;
  engineOpencodeDesc: string;
  engineAntigravityTitle: string;
  engineAntigravityDesc: string;
  demoTitle: string;
  demoDesc: string;
  demoCheckbox: string;
  demoButtonRunning: string;
  demoButtonRun: string;
  demoHeader: string;
  diagramTitle: string;
  diagramDesc: string;
  diagramStepFile: string;
  diagramStepFileDesc: string;
  diagramStepGate1: string;
  diagramStepGate1Desc: string;
  diagramStepCommit: string;
  diagramStepCommitDesc: string;
  diagramStepGate2: string;
  diagramStepGate2Desc: string;
  configTitle: string;
  configDesc: string;
  configTabPrecommit: string;
  configTabEslint: string;
  configTabCircuit: string;
  settingsTitle: string;
  settingsLang: string;
  settingsTheme: string;
  settingsThemeLight: string;
  settingsThemeDark: string;
  settingsThemeSystem: string;
  settingsColor: string;
  settingsFont: string;
  settingsFontSans: string;
  settingsFontSerif: string;
  colorBlue: string;
  colorGreen: string;
  colorOrange: string;
  colorIndigo: string;
  colorTeal: string;
  sidebarTitle: string;
  catGettingStarted: string;
  catUsage: string;
  catConfiguration: string;
  catArchitecture: string;
  catSupport: string;
  pageOverview: string;
  pageFeatures: string;
  pageStaticAnalysis: string;
  pageQuickStart: string;
  pageGate1: string;
  pageGate2: string;
  pageDemo: string;
  pageConfigJson: string;
  pageEnvVars: string;
  pageConfigExamples: string;
  pageArchitecture: string;
  pageEngines: string;
  pageTroubleshooting: string;
  pagePrev: string;
  pageNext: string;
  menuOpen: string;
  menuClose: string;
  sidebarOpen: string;
  sidebarClose: string;
}

export const translations: Record<Locale, TranslationResource> = {
  ja: {
    title: "AME-AI-Review-System",
    githubRepo: "GitHub リポジトリ",
    badgeVersion: "v0.2.12",
    heroTitle1: "デュアルゲートAIコードレビュー",
    heroTitleAccent: "厳格な静的解析とAIエージェント",
    heroTitle2: "が品質向上をサポート",
    heroDesc:
      "開発者のローカル環境（Gate 1）とプルリクエスト（Gate 2）の二重ゲート構造。mainブランチとの全累積差分評価、厳格な静的解析サーキットブレーカー、およびClaude Code / OpenCode / Antigravityなどの各種Codingエージェント連携により、コードとドキュメントの品質向上をサポートします。",
    tryDemoBtn: "シミュレーターを試す",
    viewConfigBtn: "設定ファイルを見る",
    secFeaturesTitle: "厳格さと柔軟性を備えたコアアーキテクチャ",
    secFeaturesDesc:
      "静的解析の厳格性とAIエージェントの柔軟なコンテキスト評価を融合した品質管理機構",
    featureDiffTitle: "mainブランチ累積差分レビュー",
    featureDiffDesc:
      "Commit単位の局所的な変更点ではなく origin/main...HEAD の全累積差分を評価。複数コミットを含むPRでも変更の全容を漏らさず正確に追跡・レビューします。",
    featureCbTitle: "厳格な静的サーキットブレーカー",
    featureCbDesc:
      "TypeScript (tsc)、ESLint (--max-warnings=0)、Python (mypy/ruff)、Semgrep を前段で実行。機械的指摘を高い精度で捕捉し、エラー時はAI呼び出しを即時スキップします。",
    featureGateTitle: "Dual-Gate 品質チェック",
    featureGateDesc:
      "ローカルコミット時（Gate 1）とCI/CDのPR時（Gate 2）の二段階で静的解析とAIレビューを実行。早期検出（Shift-Left）とPRでの強固なガードを両立します。",
    featureAgentTitle: "Codingエージェント & 広範コンテキスト検証",
    featureAgentDesc:
      "Claude Code, OpenCode, AntigravityなどのCodingエージェントをエンジンに指定可能。差分外を含む全リポジトリを参照し「コード修正に伴うDocumentsの更新有無」なども自動チェック可能。",
    featureLoopTitle: "停滞ループ自動検出",
    featureLoopDesc:
      "指摘内容のJaccard類似度を自動評価。進展のない堂々巡りの議論（無限ループ）を検知すると強制的にLGTMを発行しデリバリー速度の低下を防ぎます。",
    staticAnalysisTitle: "静的解析プリセット一覧",
    staticAnalysisDesc:
      "機械的に検出可能な問題は LLM 呼び出し前に静的解析で高い精度でキャッチする思想を徹底しています。以下のツール群が既定の品質チェックとして Gate 1 / Gate 2 の両方で動作します。",
    staticAnalysisStatCategories: "カテゴリ",
    staticAnalysisStatTools: "採用ツール",
    staticAnalysisConfigLabel: "主な設定ファイル",
    staticAnalysisPortabilityNote:
      "本リポジトリは、別プロジェクトへ .github/ と ame_ai_review_system/ をコピペするだけで、この静的解析構成ごと移植可能です。",
    enginesTitle: "対応 Coding エージェント",
    enginesDesc: "開発スタイルや環境に合わせて切り替え可能なマルチエンジン構造",
    engineClaudeTitle: "Claude Code",
    engineClaudeDesc:
      "Anthropic開発のエージェント。リポジトリ全域のコンテキスト参照・プロンプトキャッシュ最適化・予算上限管理に対応。",
    engineOpencodeTitle: "OpenCode",
    engineOpencodeDesc:
      "オープンソースエージェント。Anthropic, OpenRouter, DeepSeek, Tencent など多種多様なLLMプロバイダーを統合利用可能。",
    engineAntigravityTitle: "Antigravity",
    engineAntigravityDesc:
      "Google DeepMind開発の高度なAIエージェント。広範なコンテキスト検証と段階的なReasoning Effort(High/Medium/Low)に対応。",
    demoTitle: "ローカル検証の体験",
    demoDesc:
      "コミット時におけるローカル検証（ゲート1）が、どのようにコードや設定の欠陥を検知してコミットをブロックするかをシミュレートできます。以下のチェックを切り替えて、シミュレーションを実行してください。",
    demoCheckbox: "高重要度のバグコードをシミュレートする (AIレビューでの指摘を擬似発生)",
    demoButtonRunning: "検証プロセスを実行中...",
    demoButtonRun: "コミット検証を実行",
    demoHeader: "git-gate@bash: ~",
    diagramTitle: "デュアルゲート処理フロー",
    diagramDesc:
      "コード変更からコミット、PRレビューまでの最適化パイプライン（いずれかのノードを選択して詳細情報を表示）",
    diagramStepFile: "1. ファイル変更検知",
    diagramStepFileDesc: "TS / Python / MD / JSON / YAML 等",
    diagramStepGate1: "2. ゲート1 (静的解析)",
    diagramStepGate1Desc: "並行静的チェッカー実行",
    diagramStepCommit: "3. コミット実行",
    diagramStepCommitDesc: "検証通過でのみコミットを許可",
    diagramStepGate2: "4. ゲート2 (PRレビュー)",
    diagramStepGate2Desc: "/request-review による指摘",
    configTitle: "品質チェックの設定構成",
    configDesc: "チーム全体で共有され、高い品質を維持するための標準設定ファイル",
    configTabPrecommit: "pre-commit 設定",
    configTabEslint: "ESLint 設定",
    configTabCircuit: "サーキットブレーカー (Python)",
    settingsTitle: "表示設定",
    settingsLang: "言語 (Language)",
    settingsTheme: "テーマ (Theme)",
    settingsThemeLight: "ライト",
    settingsThemeDark: "ダーク",
    settingsThemeSystem: "システム",
    settingsColor: "ポイントカラー (Color)",
    settingsFont: "フォント (Font)",
    settingsFontSans: "Sans-Serif (ゴシック体)",
    settingsFontSerif: "Serif (明朝体)",
    colorBlue: "Trust Blue (青)",
    colorGreen: "Stable Green (緑)",
    colorOrange: "Grounded Orange (橙)",
    colorIndigo: "Sophisticated Indigo (藍)",
    colorTeal: "Clarity Teal (青緑)",
    sidebarTitle: "ドキュメント",
    catGettingStarted: "はじめに",
    catUsage: "使い方",
    catConfiguration: "設定",
    catArchitecture: "アーキテクチャ",
    catSupport: "サポート",
    pageOverview: "概要",
    pageFeatures: "主な機能",
    pageStaticAnalysis: "静的解析プリセット",
    pageQuickStart: "インストールと初期設定",
    pageGate1: "Gate 1: pre-commit",
    pageGate2: "Gate 2: PR レビュー",
    pageDemo: "動作デモ",
    pageConfigJson: "config.json",
    pageEnvVars: "環境変数",
    pageConfigExamples: "設定ファイル例",
    pageArchitecture: "システム構成",
    pageEngines: "Coding エージェント",
    pageTroubleshooting: "トラブルシューティング",
    pagePrev: "前へ",
    pageNext: "次へ",
    menuOpen: "メニューを開く",
    menuClose: "メニューを閉じる",
    sidebarOpen: "サイドバーを開く",
    sidebarClose: "サイドバーを閉じる",
  },
  en: {
    title: "AME-AI-Review-System",
    githubRepo: "GitHub Repo",
    badgeVersion: "v0.2.12",
    heroTitle1: "Dual-Gate AI Code Review",
    heroTitleAccent: "Strict Static Checks & AI Agents",
    heroTitle2: "Support Quality Improvement",
    heroDesc:
      "A dual-gate quality control architecture combining local pre-commit (Gate 1) and pull request reviews (Gate 2). Evaluates cumulative main branch diffs, strict static circuit breakers, and integrates Coding agents like Claude Code, OpenCode, and Antigravity to support quality improvement for code and documents.",
    tryDemoBtn: "Try Simulator",
    viewConfigBtn: "View Config Files",
    secFeaturesTitle: "Core Architecture Designed for Rigidity & Flexibility",
    secFeaturesDesc:
      "A quality management system combining strict static analysis with flexible AI agent context evaluations",
    featureDiffTitle: "Main Branch Cumulative Diff Review",
    featureDiffDesc:
      "Evaluates cumulative diffs (origin/main...HEAD) instead of per-commit fragments, capturing the full scope of multi-commit PRs accurately.",
    featureCbTitle: "Strict Static Circuit Breaker",
    featureCbDesc:
      "Executes tsc, ESLint (--max-warnings=0), mypy/ruff, and Semgrep upfront. Catches static issues early with high precision and skips AI calls when errors occur.",
    featureGateTitle: "Dual-Gate Quality Checks",
    featureGateDesc:
      "Combines local pre-commit verification (Gate 1) with CI pull request reviews (Gate 2), ensuring local Shift-Left and solid CI gating.",
    featureAgentTitle: "Coding Agent & Full Context Analysis",
    featureAgentDesc:
      "Supports Claude Code, OpenCode, and Antigravity. Refers to full repository context to automatically check if documentation updates match code changes.",
    featureLoopTitle: "Stagnation Loop Detection",
    featureLoopDesc:
      "Evaluates comment Jaccard similarity to catch circular discussions, issuing forced LGTMs to maintain team velocity.",
    staticAnalysisTitle: "Static Analysis Suite",
    staticAnalysisDesc:
      "Mechanically detectable issues are caught with high precision by static analysis before any LLM call. The tools below run as the default quality gate in both Gate 1 and Gate 2.",
    staticAnalysisStatCategories: "Categories",
    staticAnalysisStatTools: "Tools Included",
    staticAnalysisConfigLabel: "Key Config Files",
    staticAnalysisPortabilityNote:
      "Just copy .github/ and ame_ai_review_system/ into another project to port this entire static analysis setup along with it.",
    enginesTitle: "Supported Coding Agents",
    enginesDesc: "Multi-engine architecture adaptable to your team's workflow and AI stack",
    engineClaudeTitle: "Claude Code",
    engineClaudeDesc:
      "Powered by Anthropic. Features deep repository-wide context, prompt caching, and per-run budget caps.",
    engineOpencodeTitle: "OpenCode",
    engineOpencodeDesc:
      "Open-source agent engine supporting multi-provider models (Anthropic, OpenRouter, DeepSeek, Tencent, etc.).",
    engineAntigravityTitle: "Antigravity",
    engineAntigravityDesc:
      "Next-gen agent by Google DeepMind with deep context reasoning and configurable effort controls.",
    demoTitle: "Experience Local Verification",
    demoDesc:
      "Simulate how Gate 1 (pre-commit hook) catches flaws in code or configurations and blocks commits. Toggle the option below and start the verification.",
    demoCheckbox: "Simulate high-priority bug code (triggers AI review warnings)",
    demoButtonRunning: "Running verification...",
    demoButtonRun: "Run Commit Verification",
    demoHeader: "git-gate@bash: ~",
    diagramTitle: "Dual-Gate Pipeline Flow",
    diagramDesc:
      "Optimized pipeline from code modifications to commit and PR reviews (Select a node to view technical details)",
    diagramStepFile: "1. File Change Detect",
    diagramStepFileDesc: "TS / Python / MD / JSON / YAML etc.",
    diagramStepGate1: "2. Gate 1 (Static Check)",
    diagramStepGate1Desc: "Parallel static checkers execution",
    diagramStepCommit: "3. Execute Commit",
    diagramStepCommitDesc: "Allows commit execution only when local checks pass",
    diagramStepGate2: "4. Gate 2 (PR Review)",
    diagramStepGate2Desc: "Triggers AI feedback on CI via /request-review",
    configTitle: "Quality Check Settings",
    configDesc: "Shared, standard configuration files maintaining code and review policies",
    configTabPrecommit: "pre-commit Config",
    configTabEslint: "ESLint Config",
    configTabCircuit: "Circuit Breaker (Python)",
    settingsTitle: "Display Settings",
    settingsLang: "Language",
    settingsTheme: "Theme Mode",
    settingsThemeLight: "Light",
    settingsThemeDark: "Dark",
    settingsThemeSystem: "System",
    settingsColor: "Point Color",
    settingsFont: "Font",
    settingsFontSans: "Sans-Serif",
    settingsFontSerif: "Serif",
    colorBlue: "Trust Blue",
    colorGreen: "Stable Green",
    colorOrange: "Grounded Orange",
    colorIndigo: "Sophisticated Indigo",
    colorTeal: "Clarity Teal",
    sidebarTitle: "Docs",
    catGettingStarted: "Getting Started",
    catUsage: "Usage",
    catConfiguration: "Configuration",
    catArchitecture: "Architecture",
    catSupport: "Support",
    pageOverview: "Overview",
    pageFeatures: "Features",
    pageStaticAnalysis: "Static Analysis",
    pageQuickStart: "Install & Setup",
    pageGate1: "Gate 1: pre-commit",
    pageGate2: "Gate 2: PR Review",
    pageDemo: "Interactive Demo",
    pageConfigJson: "config.json",
    pageEnvVars: "Environment Variables",
    pageConfigExamples: "Config Examples",
    pageArchitecture: "Architecture",
    pageEngines: "Coding Agents",
    pageTroubleshooting: "Troubleshooting",
    pagePrev: "Previous",
    pageNext: "Next",
    menuOpen: "Open menu",
    menuClose: "Close menu",
    sidebarOpen: "Open sidebar",
    sidebarClose: "Close sidebar",
  },
};
