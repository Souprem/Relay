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
    correct: rate,
  };
}

const headline: CostData["comparison"]["headline"] = {
  claude: side("Claude Opus 5", "0.01560455", "$0.016", "$0.0156", "batch"),
  jev: side("Jev q-v0.3", "0.00017497", "$0.00017", "$0.000175", "sync"),
  ratio: { value: 89.18, rounded: 89, text: "89×", fraction_text: "1/89th" },
  text: "Cost per case on gold: Jev $0.00017 · Claude Opus 5 $0.016 (batch), about 89× more, at similar gold accuracy.",
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
      `max(2px, ${(0.00017497 / 0.01560455) * 100}%)`,
    ]);
    expect(screen.getByText("$0.0156")).toBeInTheDocument();
    expect(screen.getByText("$0.000175")).toBeInTheDocument();
  });
});
