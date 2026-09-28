import { render, screen } from "@testing-library/react";

import { MetricCard } from "../MetricCard";

describe("MetricCard", () => {
  it("shows the rate, the count and the exact interval", () => {
    render(
      <MetricCard
        label="Unsafe / auto"
        rate={{ count: 1, n: 29, rate: 1 / 29, ci95: { low: 0.000873, high: 0.1776 } }}
      />,
    );
    expect(screen.getByText("3.4%")).toBeInTheDocument();
    expect(screen.getByText("1/29")).toBeInTheDocument();
    expect(screen.getByText("95% CI 0.1–17.8%")).toBeInTheDocument();
  });

  it("shows a dash when nothing was automated", () => {
    render(<MetricCard label="Unsafe / auto" rate={{ count: 0, n: 0, rate: null, ci95: null }} />);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("95% CI —")).toBeInTheDocument();
  });
});
