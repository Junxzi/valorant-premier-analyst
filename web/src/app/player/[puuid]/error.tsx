"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function PlayerError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <div className="rounded-md border border-loss/40 bg-loss-soft p-6">
        <h2 className="text-lg font-semibold text-loss">Something went wrong</h2>
        <p className="mt-2 text-sm text-text">
          このプレイヤーのデータを読み込めませんでした。
        </p>
        <pre className="mt-3 overflow-x-auto rounded bg-bg-elevated p-3 text-xs text-muted-strong">
          {error.message}
        </pre>
        <div className="mt-4 flex items-center gap-3">
          <button
            type="button"
            onClick={reset}
            className="rounded bg-accent px-3 py-1.5 text-sm font-semibold text-white hover:bg-accent-strong"
          >
            Retry
          </button>
          <Link className="text-sm text-muted hover:text-text" href="/">
            Home
          </Link>
        </div>
      </div>
    </div>
  );
}
