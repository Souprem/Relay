import { render, screen } from "@testing-library/react";

import { CostBars } from "../CostBars";
import { CostLine } from "../CostLine";
import type { CostData } from "@/lib/types";

const rate = {
  count: 93,
  n: 100,
  rate: 0.93,
  ci95: { low: 0.861, high: 0.971 },
  pct: "93.0%",
  text: "93/100 (93.0%)",
  ci_text: "86.1–97.1%",
  ci_high_pct: "97.1%",
};

function side(label: string, perCase: string, short: string, text: string, mode: "sync" | "batch") {
  return {
    run_id: `run_${label}`,
    label,
    question_set: "q",
    mode,
    n: 100,
    per_case_usd: perCase,
    per_case_text: text,
    per_case_short: short,
    total_text: "$1",
    source: "ledger",
    kind: (label.startsWith("Jev") ? "trace-estimate" : "ledger") as "trace-estimate" | "ledger",
    estimate_label: label.startsWith("Jev") ? "trace estimate" : null,
    correct: rate,
  };
}

const headline: CostData["comparison"]["headline"] = {
  claude: side("Claude Opus 5", "0.01560455", "$0.016", "$0.0156", "batch"),
  jev: side("Jev q-v0.2", "0.00011513082", "$0.00012", "$0.000115", "sync"),
  ratio: { value: 135.54, rounded: 136, text: "136×", fraction_text: "1/136th" },
  text:
    "Cost per case on gold, same questions: Jev q-v0.2 $0.000115 (trace estimate) · Claude Opus 5 $0.0156 (batch), about 136× more, at similar gold accuracy.",
  estimate_note: "From the traces' estimated cost.",
  summary: "",
};

describe("CostLine", () => {
  it("reads exactly as the exported sentence and links to the cost section", () => {
    render(<CostLine headline={headline} />);
    expect(screen.getByTestId("cost-sentence").textContent).toBe(headline.text);
    expect(screen.getByRole("link", { name: "Cost and speed →" })).toHaveAttribute("href", expect.stringMatching(/^\/experiments\/?#cost$/));
  });
});

describe("CostBars", () => {
  it("draws the longer bar full width and the shorter one at its true fraction", () => {
    const { container } = render(<CostBars headline={headline} />);
    const bars = [...container.querySelectorAll<HTMLElement>("dd span[style]")];
    expect(bars.map((b) => b.style.width)).toEqual([
      "max(2px, 100%)",
      `max(2px, ${(0.00011513082 / 0.01560455) * 100}%)`,
    ]);
    expect(screen.getByText("$0.0156")).toBeInTheDocument();
    expect(screen.getByText("$0.000115")).toBeInTheDocument();
    expect(screen.getByText("Jev q-v0.2, sync (trace estimate)")).toBeInTheDocument();
  });
});
