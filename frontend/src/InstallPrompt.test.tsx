import { test, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import InstallPrompt from "./InstallPrompt";

function fireBeforeInstallPrompt() {
  const event = new Event("beforeinstallprompt", { cancelable: true }) as Event & {
    prompt: () => Promise<void>;
    userChoice: Promise<{ outcome: string }>;
  };
  event.prompt = () => Promise.resolve();
  event.userChoice = Promise.resolve({ outcome: "accepted" });
  fireEvent(window, event);
}

test("renders nothing until beforeinstallprompt fires", () => {
  render(<InstallPrompt />);
  expect(screen.queryByText("설치")).toBeNull();

  fireBeforeInstallPrompt();
  expect(screen.getByText("설치")).toBeDefined();
});

test("닫기 button hides the banner", () => {
  render(<InstallPrompt />);
  fireBeforeInstallPrompt();
  expect(screen.getByText("설치")).toBeDefined();

  fireEvent.click(screen.getByText("닫기"));
  expect(screen.queryByText("설치")).toBeNull();
});
