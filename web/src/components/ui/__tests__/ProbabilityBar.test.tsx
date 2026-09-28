import { render, screen } from "@testing-library/react";

import { ProbabilityBar } from "../ProbabilityBar";

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
