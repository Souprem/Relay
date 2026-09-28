import Link from "next/link";

export default function NotFound() {
  return (
    <div className="max-w-prose">
      <p className="text-label font-semibold uppercase text-ink-2">404</p>
      <h1 className="mt-1 text-xl font-medium text-ink">No page at this address</h1>
      <p className="mt-2 text-md text-ink-2">
        Case pages exist for the 100 gold and 10 smoke cases. Find one in the{" "}
        <Link href="/cases/" className="underline hover:text-ink">
          case table
        </Link>
        .
      </p>
    </div>
  );
}
