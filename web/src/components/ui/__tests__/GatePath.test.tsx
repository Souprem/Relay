import { render, screen, within } from "@testing-library/react";

import type { GateRow } from "@/lib/types";

import { GatePath } from "../GatePath";

const GATES: GateRow[] = [
  { gate: "provider", status: "passed", detail: "all five decisions present and well-formed" },
  { gate: "age", status: "passed", detail: "patient.age=60, policy min_age=18" },
  { gate: "contradiction", status: "FIRED", detail: "p_yes(material_contradiction)=0.910, review at >= 0.8" },
  { gate: "documentation", status: "not reached", detail: null },
  { gate: "missing_evidence", status: "not reached", detail: null },
  { gate: "auto_process", status: "not reached", detail: null },
  { gate: "default_review", status: "not reached", detail: null },
];

describe("GatePath", () => {
  it("renders every gate in engine order", () => {
    render(<GatePath gates={GATES} />);
    const items = within(screen.getByRole("list", { name: "Gate path" })).getAllByRole("listitem");
    expect(items.map((li) => li.getAttribute("data-status"))).toEqual([
      "passed",
      "passed",
      "FIRED",
      "not reached",
      "not reached",
      "not reached",
      "not reached",
    ]);
  });

  it("names the action the fired gate produced, with its detail", () => {
    render(<GatePath gates={GATES} />);
    const fired = screen.getAllByRole("listitem")[2];
    expect(fired).toHaveTextContent("FIRED → HUMAN_REVIEW");
    expect(fired).toHaveTextContent("review at >= 0.8");
  });

  it("marks the gates after the fired one as not reached, without detail", () => {
    render(<GatePath gates={GATES} />);
    const last = screen.getAllByRole("listitem")[6];
    expect(last).toHaveTextContent("default_review");
    expect(last).toHaveTextContent("not reached");
    expect(last.querySelector("p")).toBeNull();
  });
});
