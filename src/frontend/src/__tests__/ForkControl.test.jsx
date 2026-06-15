import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ForkControl from "../components/ForkControl.jsx";

describe("ForkControl", () => {
  it("renders Subir and Descer buttons", () => {
    render(<ForkControl />);
    expect(screen.getByText("Subir")).toBeInTheDocument();
    expect(screen.getByText("Descer")).toBeInTheDocument();
  });

  it("sends subir on pointerdown", () => {
    const handler = vi.fn();
    render(<ForkControl onForkCommand={handler} />);
    fireEvent.pointerDown(screen.getByText("Subir"));
    expect(handler).toHaveBeenCalledWith("subir");
  });

  it("sends parar on pointerup", () => {
    const handler = vi.fn();
    render(<ForkControl onForkCommand={handler} />);
    fireEvent.pointerUp(screen.getByText("Subir"));
    expect(handler).toHaveBeenCalledWith("parar");
  });

  it("sends descer on pointerdown", () => {
    const handler = vi.fn();
    render(<ForkControl onForkCommand={handler} />);
    fireEvent.pointerDown(screen.getByText("Descer"));
    expect(handler).toHaveBeenCalledWith("descer");
  });
});
