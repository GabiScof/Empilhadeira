import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ModeSelector from "../components/ModeSelector.jsx";

describe("ModeSelector", () => {
  it("renders three mode buttons", () => {
    render(<ModeSelector currentMode="PARADO" />);
    expect(screen.getByText("MANUAL")).toBeInTheDocument();
    expect(screen.getByText("AUTOMATICO")).toBeInTheDocument();
    expect(screen.getByText("PARADO")).toBeInTheDocument();
  });

  it("highlights the active mode", () => {
    render(<ModeSelector currentMode="MANUAL" />);
    const btn = screen.getByText("MANUAL");
    expect(btn.className).toContain("bg-blue-600");
  });

  it("calls onModeChange when clicked", () => {
    const handler = vi.fn();
    render(<ModeSelector currentMode="PARADO" onModeChange={handler} />);
    fireEvent.click(screen.getByText("MANUAL"));
    expect(handler).toHaveBeenCalledWith("MANUAL");
  });

  it("disables buttons when disabled prop is true", () => {
    render(<ModeSelector currentMode="PARADO" disabled />);
    expect(screen.getByText("MANUAL")).toBeDisabled();
  });
});
