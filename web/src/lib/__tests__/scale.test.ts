import { linear, niceMax, niceTicks } from "../scale";

describe("scales", () => {
  it("maps a domain onto a range, including an inverted one", () => {
    const y = linear([0, 1], [100, 0]);
    expect(y(0)).toBe(100);
    expect(y(0.25)).toBe(75);
    expect(linear([2, 2], [0, 10])(5)).toBe(0);
  });

  it("makes nice ticks and maxima", () => {
    expect(niceTicks(0, 0.5, 5)).toEqual([0, 0.1, 0.2, 0.3, 0.4, 0.5]);
    expect(niceTicks(0, 400, 4)).toEqual([0, 100, 200, 300, 400]);
    expect(niceMax(0.33)).toBe(0.5);
    expect(niceMax(0.062)).toBe(0.1);
  });
});
