import { render, screen } from "@testing-library/react";

import { ActionBadge } from "../ActionBadge";
import { VerdictCell, VerdictLabel } from "../Verdict";

describe("verdict colouring", () => {
  it("marks an unsafe automation in red, with words for screen readers", () => {
    const { container } = render(<VerdictCell action="AUTO_PROCESS" verdict="UNSAFE" />);
    const cell = container.querySelector("[data-verdict]")!;
    expect(cell).toHaveAttribute("data-verdict", "UNSAFE");
    expect(cell.className).toContain("text-unsafe");
    expect(cell.className).toContain("bg-unsafe-tint");
    expect(cell).toHaveTextContent("AUTO, unsafe");
  });

  it("hatches a wrong but safe action and never colours it red", () => {
    const { container } = render(<VerdictCell action="HUMAN_REVIEW" verdict="wrong-safe" />);
    const cell = container.querySelector("[data-verdict]")!;
    expect(cell.className).toContain("hatch");
    expect(cell.className).not.toContain("unsafe");
    expect(cell.className).toContain("text-review");
    expect(cell).toHaveTextContent("REVIEW, wrong but safe");
  });

  it("gives a correct action its action colour and no background", () => {
    const { container } = render(<VerdictCell action="REQUEST_INFO" verdict="correct" />);
    const cell = container.querySelector("[data-verdict]")!;
    expect(cell.className).toContain("text-info");
    expect(cell.className).not.toContain("hatch");
    expect(cell.className).not.toContain("bg-");
  });

  it("names the verdict in words", () => {
    render(<VerdictLabel verdict="UNSAFE" />);
    expect(screen.getByText("UNSAFE").className).toContain("text-unsafe");
  });

  it("shows each action with its own colour token", () => {
    render(<ActionBadge action="HUMAN_REVIEW" />);
    const badge = screen.getByText("HUMAN_REVIEW");
    expect(badge).toHaveAttribute("data-action", "HUMAN_REVIEW");
    expect(badge.className).toContain("text-review");
  });
});
