import { render, screen } from "@testing-library/react";

import { MIN_TRACK_PX, ProbabilityBar, tickLabel, tickRows } from "../ProbabilityBar";

describe("ProbabilityBar", () => {
  it("draws a tick at each threshold, positioned at its value", () => {
    render(
      <ProbabilityBar
        label="Documentation complete"
        value={0.97}
        ticks={[
          { name: "auto_process", value: 0.89 },
          { name: "documentation_request_info", value: 0.6 },
        ]}
      />,
    );
    expect(screen.getByTestId("tick-auto_process")).toHaveStyle({ left: "89.00%" });
    expect(screen.getByTestId("tick-documentation_request_info")).toHaveStyle({ left: "60.00%" });
    expect(screen.getByTestId("tick-auto_process")).toHaveTextContent("auto 0.89");
    expect(screen.getByTestId("bar-fill")).toHaveStyle({ width: "97.00%" });
  });

  it("describes the value and thresholds for screen readers", () => {
    render(<ProbabilityBar label="Step therapy met" value={0.9316} ticks={[{ name: "auto_process", value: 0.89 }]} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("Step therapy met: 0.932; auto threshold 0.89");
    expect(screen.getByText("0.932")).toBeInTheDocument();
  });

  it("shows a missing judgment without a fill", () => {
    render(<ProbabilityBar label="Diagnosis supported" value={null} ticks={[]} />);
    expect(screen.queryByTestId("bar-fill")).toBeNull();
    expect(screen.getByText("missing")).toBeInTheDocument();
  });
});

describe("tick label collisions", () => {
  it("puts a label below the track when it would overlap its neighbour (q-v0.3: 0.60 and 0.81)", () => {
    const ticks = [
      { name: "auto_process", value: 0.81 },
      { name: "documentation_request_info", value: 0.6 },
    ];
    expect(tickRows(ticks)).toEqual([1, 0]);
    render(<ProbabilityBar label="Documentation complete" value={0.97} ticks={ticks} />);
    expect(screen.getByTestId("tick-documentation_request_info")).toHaveAttribute("data-row", "0");
    expect(screen.getByTestId("tick-auto_process")).toHaveAttribute("data-row", "1");
    expect(screen.getByTestId("tick-auto_process")).toHaveTextContent("auto 0.81");
  });

  it("staggers 0.60 and 0.89 too, which touch on a phone", () => {
    expect(tickRows([
      { name: "documentation_request_info", value: 0.6 },
      { name: "auto_process", value: 0.89 },
    ])).toEqual([0, 1]);
  });

  it("keeps well-separated labels on one row", () => {
    expect(tickRows([
      { name: "contradiction_auto_block", value: 0.2 },
      { name: "contradiction_review", value: 0.8 },
    ])).toEqual([0, 0]);
    expect(tickRows([{ name: "auto_process", value: 0.89 }])).toEqual([0]);
  });

  it("never lets two labels in the same row overlap on the narrowest track", () => {
    const names = ["auto_process", "documentation_request_info", "contradiction_review", "contradiction_auto_block"];
    for (let a = 0.05; a < 1; a += 0.05) {
      for (let b = 0.05; b < 1; b += 0.05) {
        const ticks = [
          { name: names[0], value: a },
          { name: names[1], value: b },
        ];
        const rows = tickRows(ticks);
        if (rows[0] !== rows[1]) continue;
        const ext = ticks.map((t) => {
          const w = tickLabel(t).length * 7.3;
          const x = t.value * MIN_TRACK_PX;
          return t.value > 0.9 ? [x - w, x] : t.value < 0.1 ? [x, x + w] : [x - w / 2, x + w / 2];
        });
        const [l, r] = ext[0][0] < ext[1][0] ? ext : [ext[1], ext[0]];
        expect(r[0]).toBeGreaterThanOrEqual(l[1]);
      }
    }
  });
});
