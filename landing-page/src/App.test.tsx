import { render, screen, fireEvent, act, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import App from "./App";
import { DRAWER_EXIT_MS } from "./animationTiming";

const openPage = (label: string): void => {
  const matches = screen.getAllByRole("button", { name: label });
  if (matches[0]) {
    fireEvent.click(matches[0]);
  }
};

describe("App Component", () => {
  beforeEach(() => {
    localStorage.clear();
    window.location.hash = "";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("renders the Japanese titles and documentation navigation", () => {
    render(<App />);
    expect(screen.getByRole("button", { name: /AME-AI-Review-System/ })).toBeInTheDocument();
    expect(screen.getByText(/デュアルゲートAIコードレビュー/)).toBeInTheDocument();
    expect(screen.getByText(/厳格な静的解析とAIエージェント/)).toBeInTheDocument();
    expect(screen.getByText("ドキュメント")).toBeInTheDocument();
  });

  it("shows the current version badge", () => {
    render(<App />);
    expect(screen.getAllByText("v0.2.14").length).toBeGreaterThan(0);
  });

  it("renders the hero header image on the overview page", () => {
    render(<App />);
    expect(screen.getByRole("img", { name: "AME-AI-Review-System" })).toBeInTheDocument();
  });

  it("renders the static analysis suite section via sidebar navigation", () => {
    render(<App />);
    openPage("静的解析プリセット");
    expect(screen.getByRole("heading", { name: "静的解析プリセット" })).toBeInTheDocument();
    expect(screen.getByText("ruff (lint, ALL+preview)")).toBeInTheDocument();
    expect(screen.getByText("semgrep-custom (8 rules)")).toBeInTheDocument();
  });

  it("renders detailed documentation pages via sidebar navigation", () => {
    render(<App />);
    openPage("インストールと初期設定");
    expect(screen.getByRole("heading", { name: "インストールと初期設定" })).toBeInTheDocument();
    expect(screen.getAllByText(/ame-ai-reviewer init/).length).toBeGreaterThan(0);

    openPage("config.json");
    expect(screen.getByRole("heading", { name: "config.json" })).toBeInTheDocument();
    expect(screen.getByText("precommit_review_enabled")).toBeInTheDocument();
  });

  it("toggles the simulated bug checkbox on the demo page", () => {
    render(<App />);
    openPage("動作デモ");
    const checkbox = screen.getByLabelText(
      "高重要度のバグコードをシミュレートする (AIレビューでの指摘を擬似発生)"
    );
    expect(checkbox).not.toBeChecked();
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });

  it("runs the simulator sequence successfully", () => {
    vi.useFakeTimers();
    render(<App />);
    openPage("動作デモ");

    // Initial logs check
    expect(
      screen.getByText("--- AME AI Review System インタラクティブ・シミュレーター ---")
    ).toBeInTheDocument();

    const runBtn = screen.getByRole("button", { name: "コミット検証を実行" });
    fireEvent.click(runBtn);

    // After clicking, verify initial logs are printed
    expect(screen.getByText("git add .")).toBeInTheDocument();
    expect(
      screen.getByText(
        "検証対象ファイルをステージング中: landing-page/src/App.tsx, pyproject.toml, README.md"
      )
    ).toBeInTheDocument();

    // Fast-forward through timers
    act(() => {
      vi.advanceTimersByTime(1000); // pre-commit run
    });
    expect(screen.getByText("pre-commit run")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1000); // static precheck
    });
    expect(screen.getByText("[static-precheck] 静的解析を実行中...")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(6000); // remaining steps to complete
    });
    expect(
      screen.getByText("[git] 1ファイル変更、24行挿入(+)。コミットが成功しました！")
    ).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("runs the simulator sequence with simulated bug and blocks commit", () => {
    vi.useFakeTimers();
    render(<App />);
    openPage("動作デモ");

    const checkbox = screen.getByLabelText(
      "高重要度のバグコードをシミュレートする (AIレビューでの指摘を擬似発生)"
    );
    fireEvent.click(checkbox);

    const runBtn = screen.getByRole("button", { name: "コミット検証を実行" });
    fireEvent.click(runBtn);

    // Fast-forward through timers
    act(() => {
      vi.advanceTimersByTime(8000);
    });
    expect(screen.getByText(/コミットがブロックされました。/)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("collapses and expands the desktop sidebar", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn((query: string): MediaQueryList => ({
        matches: true,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(() => false),
      }))
    );
    render(<App />);
    expect(screen.getByTestId("desktop-sidebar")).toBeInTheDocument();

    const closeBtn = screen.getByRole("button", { name: "サイドバーを閉じる" });
    expect(closeBtn).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(closeBtn);
    const openBtn = screen.getByRole("button", { name: "サイドバーを開く" });
    expect(openBtn).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(openBtn);
    expect(screen.getByRole("button", { name: "サイドバーを閉じる" })).toHaveAttribute(
      "aria-expanded",
      "true"
    );
  });

  it("opens and closes the mobile sidebar drawer with Escape", () => {
    vi.useFakeTimers();
    render(<App />);
    const menuBtn = screen.getByRole("button", { name: "メニューを開く" });
    fireEvent.click(menuBtn);
    const dialog = screen.getByRole("dialog", { name: "ドキュメント" });
    expect(dialog).toBeInTheDocument();
    expect(dialog).not.toHaveAttribute("inert");
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(dialog).toHaveAttribute("inert");
    act(() => {
      vi.advanceTimersByTime(DRAWER_EXIT_MS);
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("traps Tab focus within the mobile sidebar drawer", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "メニューを開く" }));
    const dialog = screen.getByRole("dialog", { name: "ドキュメント" });
    const firstNav = within(dialog).getAllByRole("button", { name: "概要" })[0];
    const lastNav = within(dialog).getAllByRole("button", { name: "トラブルシューティング" })[0];
    if (firstNav === undefined || lastNav === undefined) {
      throw new Error("drawer nav buttons not found");
    }
    // Focus moves into the drawer on open
    expect(document.activeElement).toBe(firstNav);

    // Tab from the last element wraps to the first
    lastNav.focus();
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(document.activeElement).toBe(firstNav);

    // Shift+Tab from the first element wraps to the last
    firstNav.focus();
    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(lastNav);
  });

  it("changes theme mode setting (light/dark/system)", () => {
    render(<App />);
    const settingsBtn = screen.getByRole("button", { name: "表示設定" });
    fireEvent.click(settingsBtn);

    expect(screen.getByText("テーマ (Theme)")).toBeInTheDocument();
    const lightBtn = screen.getByRole("button", { name: "ライト" });
    fireEvent.click(lightBtn);

    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(document.documentElement).not.toHaveClass("dark");

    const darkBtn = screen.getByRole("button", { name: "ダーク" });
    fireEvent.click(darkBtn);

    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(document.documentElement).toHaveClass("dark");
  });
});
