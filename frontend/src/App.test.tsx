import { test, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./App";

test("renders tab bar", () => {
  render(<App />);
  expect(screen.getByText("내 데이터")).toBeDefined();
  expect(screen.getByText("캘린더")).toBeDefined();
  expect(screen.getByText("영양제")).toBeDefined();
});
