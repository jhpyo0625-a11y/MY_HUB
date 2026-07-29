import { test, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import App from "./App";

// MyDataPage fetches real API endpoints on mount; stub fetch so those calls
// resolve instead of leaving unhandled rejections (node fetch needs absolute URLs).
beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const body = url.toString().includes("/api/metrics/definitions") ? "[]" : "{}";
      return Promise.resolve(
        new Response(body, { status: 200, headers: { "Content-Type": "application/json" } })
      );
    })
  );
});
afterEach(() => vi.unstubAllGlobals());

test("renders tab bar", () => {
  render(<App />);
  const nav = within(screen.getByRole("navigation"));
  expect(nav.getByText("내 데이터")).toBeDefined();
  expect(nav.getByText("캘린더")).toBeDefined();
  expect(nav.getByText("영양제")).toBeDefined();
  expect(nav.getByText("리포트")).toBeDefined();
});
