import { act, render, screen } from "@testing-library/react";

import { Disclosure } from "../Disclosure";

function details(container: HTMLElement): HTMLDetailsElement {
  const el = container.querySelector("details");
  if (!el) throw new Error("no <details>");
  return el;
}

describe("Disclosure", () => {
  afterEach(() => {
    window.history.replaceState(null, "", "/");
  });

  it("renders closed by default, with its label and count in the summary", () => {
    const { container } = render(
      <Disclosure label="Calibration" meta="5 charts">
        <p>hidden content</p>
      </Disclosure>,
    );
    const el = details(container);
    expect(el.open).toBe(false);
    const summary = container.querySelector("summary");
    expect(summary).toHaveTextContent("Calibration");
    expect(summary).toHaveTextContent("5 charts");
    // Still in the document, so find-in-page and screen readers can reach it once opened.
    expect(screen.getByText("hidden content")).toBeInTheDocument();
  });

  it("opens when the URL hash names an element inside it", () => {
    window.history.replaceState(null, "", "/#inner");
    const { container } = render(
      <Disclosure label="Details">
        <p id="inner">deep-linked</p>
      </Disclosure>,
    );
    expect(details(container).open).toBe(true);
  });

  it("opens when the hash is one of its hashIds, and stays closed for other hashes", () => {
    window.history.replaceState(null, "", "/#elsewhere");
    const { container } = render(
      <>
        <section id="ablation" />
        <Disclosure label="Show details" hashIds={["ablation"]}>
          <p>table</p>
        </Disclosure>
      </>,
    );
    const el = details(container);
    expect(el.open).toBe(false);
    act(() => {
      window.history.replaceState(null, "", "/#ablation");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(el.open).toBe(true);
  });

  it("opens when the hash is its own id", () => {
    window.history.replaceState(null, "", "/#all-gates");
    const { container } = render(
      <Disclosure id="all-gates" label="All 20 gates">
        <p>rows</p>
      </Disclosure>,
    );
    expect(details(container).open).toBe(true);
  });
});
