import { describe, it, expect } from "vitest";
import { render } from "@testing-library/svelte";
import StatusIndicator from "./StatusIndicator.svelte";

describe("StatusIndicator", () => {
  it("should render green indicator when connected", () => {
    const { container } = render(StatusIndicator, {
      props: { connected: true },
    });

    const indicator = container.querySelector(
      '[data-testid="status-indicator"]'
    );
    expect(indicator).toBeTruthy();
    expect(indicator?.classList.contains("bg-green-500")).toBe(true);
  });

  it("should render red indicator when disconnected", () => {
    const { container } = render(StatusIndicator, {
      props: { connected: false },
    });

    const indicator = container.querySelector(
      '[data-testid="status-indicator"]'
    );
    expect(indicator).toBeTruthy();
    expect(indicator?.classList.contains("bg-red-500")).toBe(true);
  });

  it("should have proper accessibility attributes", () => {
    const { container } = render(StatusIndicator, {
      props: { connected: true },
    });

    const indicator = container.querySelector(
      '[data-testid="status-indicator"]'
    );
    expect(indicator?.getAttribute("aria-label")).toBeTruthy();
    expect(indicator?.getAttribute("role")).toBe("status");
  });

  it("should be touch-friendly size for mobile", () => {
    const { container } = render(StatusIndicator, {
      props: { connected: true },
    });

    const indicator = container.querySelector(
      '[data-testid="status-indicator"]'
    );
    expect(indicator?.classList.contains("w-3")).toBe(true);
    expect(indicator?.classList.contains("h-3")).toBe(true);
  });
});
