import Link from "next/link";

export default function PlayerNotFound() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <div className="rounded-md border border-border bg-panel p-6">
        <p className="text-xs uppercase tracking-wider text-muted">404</p>
        <h2 className="mt-1 text-2xl font-semibold text-text-strong">
          Player not found
        </h2>
        <p className="mt-3 text-sm text-muted">
          指定された puuid のプレイヤーは DuckDB に見つかりませんでした。
        </p>
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
