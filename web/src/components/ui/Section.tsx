/** A labelled section: small uppercase label, optional title and lede. */
export function Section({
  id,
  label,
  title,
  lede,
  children,
  className = "",
}: {
  id?: string;
  label: string;
  title?: React.ReactNode;
  lede?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section id={id} aria-labelledby={id ? `${id}-label` : undefined} className={`mt-6 ${className}`}>
      <div className="border-t border-rule pt-2">
        <h2 id={id ? `${id}-label` : undefined} className="text-label font-semibold uppercase text-ink-2">
          {label}
        </h2>
        {title ? <p className="mt-1 max-w-prose text-balance text-lg text-ink">{title}</p> : null}
        {lede ? <div className="mt-1 max-w-prose text-md text-ink-2">{lede}</div> : null}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function PageHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <header className="max-w-prose">
      <p className="text-label font-semibold uppercase text-ink-2">{eyebrow}</p>
      <h1 className="mt-1 text-balance text-xl font-medium text-ink">{title}</h1>
      {children ? <div className="mt-2 text-md text-ink-2">{children}</div> : null}
    </header>
  );
}
