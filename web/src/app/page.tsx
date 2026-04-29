import Link from "next/link";

export default function Home() {
  const defaultName = process.env.DEFAULT_TEAM_NAME ?? "";
  const defaultTag = process.env.DEFAULT_TEAM_TAG ?? "";
  const hasDefault = Boolean(defaultName && defaultTag);
  const teamHref = hasDefault
    ? `/team/${encodeURIComponent(defaultName)}/${encodeURIComponent(defaultTag)}`
    : null;

  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-semibold tracking-tight text-text-strong">
        Premier Team Dashboard
      </h1>
      <p className="mt-3 text-sm text-muted">
        vlr.gg風の分析ツール作りました。
      </p>

      <div className="mt-10 rounded-md border border-border bg-panel p-6">
        {hasDefault && teamHref ? (
          <>
            <p className="text-xs uppercase tracking-wider text-muted">
              Configured Team
            </p>
            <p className="mt-2 text-2xl font-semibold text-text-strong">
              {defaultName}
              <span className="ml-2 text-base font-normal text-muted">
                #{defaultTag}
              </span>
            </p>
            <Link
              href={teamHref}
              className="mt-6 inline-flex items-center gap-2 rounded bg-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent-strong"
            >
              View Team
              <span aria-hidden>→</span>
            </Link>
          </>
        ) : (
          <>
            <p className="text-sm text-muted-strong">
              <code className="rounded bg-bg-elevated px-1.5 py-0.5 text-xs">
                web/.env.local
              </code>{" "}
              に <code>DEFAULT_TEAM_NAME</code> と <code>DEFAULT_TEAM_TAG</code>{" "}
              を設定するとここに表示されます。
            </p>
            <p className="mt-3 text-sm text-muted">
              直接 URL を叩いてアクセスすることもできます:
            </p>
            <pre className="mt-2 overflow-x-auto rounded bg-bg-elevated p-3 text-xs text-muted-strong">
              /team/&lt;NAME&gt;/&lt;TAG&gt;
            </pre>
          </>
        )}
      </div>
    </div>
  );
}
