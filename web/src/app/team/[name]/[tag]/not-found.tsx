import Link from "next/link";

export default function TeamNotFound() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <div className="rounded-md border border-border bg-panel p-6">
        <p className="text-xs uppercase tracking-wider text-muted">404</p>
        <h2 className="mt-1 text-2xl font-semibold text-text-strong">
          Team not found
        </h2>
        <p className="mt-3 text-sm text-muted">
          指定された Premier チームは DuckDB に見つかりませんでした。
          まだバックフィルしていない場合は、プロジェクトルートで:
        </p>
        <pre className="mt-3 overflow-x-auto rounded bg-bg-elevated p-3 text-xs text-muted-strong">
{`python -m valorant_analyst.cli team-backfill
python -m valorant_analyst.cli ingest --from-archive`}
        </pre>
        <Link
          href="/"
          className="mt-4 inline-flex items-center gap-1 text-sm text-accent hover:text-accent-strong"
        >
          ← Home に戻る
        </Link>
      </div>
    </div>
  );
}
