// Table cells on the 8px grid: 1px rules, no fills, numbers right-aligned in tabular mono so
// decimal points line up down a column.

export function Th({
  children,
  align = "left",
  className = "",
  ...rest
}: React.ThHTMLAttributes<HTMLTableCellElement> & { align?: "left" | "right" }) {
  return (
    <th
      scope="col"
      className={`border-b border-ink py-1 pr-2 align-bottom text-label font-semibold uppercase text-ink-2 last:pr-0 ${
        align === "right" ? "text-right" : "text-left"
      } ${className}`}
      {...rest}
    >
      {children}
    </th>
  );
}

export function Td({
  children,
  num = false,
  className = "",
  ...rest
}: React.TdHTMLAttributes<HTMLTableCellElement> & { num?: boolean }) {
  return (
    <td
      className={`border-b border-rule py-1 pr-2 align-baseline last:pr-0 ${
        num ? "num text-right text-sm" : "text-base"
      } ${className}`}
      {...rest}
    >
      {children}
    </td>
  );
}

/** On a phone, a visible cue that the table below scrolls sideways. */
export function ScrollHint({ children = "Scroll sideways for every column →" }: { children?: React.ReactNode }) {
  return (
    <p aria-hidden="true" className="mb-0.5 text-label tracking-normal text-ink-3 md:hidden">
      {children}
    </p>
  );
}

/** Horizontal scroll on narrow screens instead of squashing columns. `relative` keeps the
 * absolutely positioned screen-reader text inside the scroll box. `hint` shows ScrollHint on a
 * phone, for tables wider than one. */
export function TableScroll({ children, hint = false }: { children: React.ReactNode; hint?: boolean }) {
  return (
    <>
      {hint ? <ScrollHint /> : null}
      <div className="relative -mx-3 overflow-x-auto px-3 md:mx-0 md:px-0">{children}</div>
    </>
  );
}
