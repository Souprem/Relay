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

/** Horizontal scroll on narrow screens instead of squashing columns. `relative` keeps the
 * absolutely positioned screen-reader text inside the scroll box. */
export function TableScroll({ children }: { children: React.ReactNode }) {
  return <div className="relative -mx-3 overflow-x-auto px-3 md:mx-0 md:px-0">{children}</div>;
}
