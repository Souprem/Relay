import { Disclosure } from "@/components/ui/Disclosure";

/** The data behind a chart, as a table, for screen readers and for anyone who wants the numbers. */
export function ChartData({
  summary = "Data table",
  columns,
  rows,
}: {
  summary?: string;
  columns: string[];
  rows: (string | number)[][];
}) {
  return (
    <Disclosure label={summary} meta={`${rows.length} rows`} variant="inline" className="mt-1 text-sm">
      <div className="max-h-[24rem] overflow-auto border-t border-rule">
        <table className="w-full">
          <thead>
            <tr>
              {columns.map((c, i) => (
                <th
                  key={c}
                  scope="col"
                  className={`border-b border-rule py-0.5 pr-2 text-label font-semibold uppercase text-ink-2 ${
                    i === 0 ? "text-left" : "text-right"
                  }`}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, r) => (
              <tr key={r} className="border-b border-rule">
                {row.map((cell, i) => (
                  <td key={i} className={`num py-0.5 pr-2 ${i === 0 ? "text-left" : "text-right"}`}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Disclosure>
  );
}
