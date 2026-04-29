import type { ReactNode } from "react";

type Props = {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  /** Remove built-in padding so children can render edge-to-edge tables. */
  flush?: boolean;
};

export function Card({ title, action, children, className = "", flush = false }: Props) {
  return (
    <section
      className={`rounded-md border border-border bg-panel ${className}`}
    >
      {(title || action) && (
        <header className="flex items-center justify-between border-b border-border px-4 py-2.5">
          {title ? (
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-strong">
              {title}
            </h2>
          ) : <span />}
          {action}
        </header>
      )}
      <div className={flush ? "" : "p-4"}>{children}</div>
    </section>
  );
}
