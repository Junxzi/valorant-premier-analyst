"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { API_BASE_URL } from "@/lib/api";

type SyncStatus = {
  running: boolean;
  last_started_at: string | null;
  last_finished_at: string | null;
  last_status: "ok" | "error" | null;
  last_log: string;
};

export function SyncButton() {
  const router = useRouter();
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [showLog, setShowLog] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wasRunningRef = useRef(false);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/sync`);
      if (res.ok) {
        const next: SyncStatus = await res.json();
        setStatus(next);
        return next;
      }
    } catch {}
    return null;
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  // Poll while running; refresh page data when done
  useEffect(() => {
    if (status?.running) {
      wasRunningRef.current = true;
      pollRef.current = setInterval(async () => {
        const next = await fetchStatus();
        if (next && !next.running && wasRunningRef.current) {
          wasRunningRef.current = false;
          router.refresh(); // re-fetch server component data
        }
      }, 2000);
    } else {
      if (pollRef.current) clearInterval(pollRef.current);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [status?.running, router]);

  const handleSync = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/sync`, { method: "POST" });
      if (res.ok) setStatus(await res.json());
    } catch {}
  };

  const running = status?.running ?? false;
  const lastOk = status?.last_status === "ok";
  const lastErr = status?.last_status === "error";

  const finishedAt = status?.last_finished_at
    ? new Date(status.last_finished_at).toLocaleTimeString("ja-JP", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  return (
    <div className="relative flex items-center gap-2">
      <button
        onClick={handleSync}
        disabled={running}
        title={running ? "同期中…" : "最新の試合データを取得"}
        className={`flex items-center gap-1.5 rounded-md border px-3 py-1 text-[11px] font-semibold uppercase tracking-wider transition-colors disabled:cursor-not-allowed ${
          running
            ? "border-accent/40 text-accent/60"
            : lastErr
              ? "border-loss/60 text-loss hover:bg-loss-soft"
              : "border-border text-muted hover:text-text hover:border-border/80"
        }`}
      >
        {/* Icon */}
        <svg
          viewBox="0 0 16 16"
          fill="currentColor"
          className={`w-3.5 h-3.5 ${running ? "animate-spin" : ""}`}
        >
          {running ? (
            // Spinner arc
            <path d="M8 1a7 7 0 1 0 7 7h-2a5 5 0 1 1-5-5V1z" />
          ) : (
            // Sync arrows
            <path d="M13.65 2.35A8 8 0 1 0 15 8h-2a6 6 0 1 1-1.05-3.42L10 6h5V1l-1.35 1.35z" />
          )}
        </svg>
        {running ? "Sync中" : "Sync"}
      </button>

      {/* Last result indicator */}
      {!running && finishedAt && (
        <button
          onClick={() => setShowLog((v) => !v)}
          title="最終同期ログを見る"
          className={`text-[10px] tabular-nums ${lastOk ? "text-win" : "text-loss"}`}
        >
          {lastOk ? "✓" : "✗"} {finishedAt}
        </button>
      )}

      {/* Log dropdown */}
      {showLog && status?.last_log && (
        <div className="absolute top-full right-0 mt-1 z-50 w-96 max-h-64 overflow-auto rounded-md border border-border bg-panel shadow-lg">
          <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
            <span className="text-[10px] uppercase tracking-wider text-muted">Sync Log</span>
            <button onClick={() => setShowLog(false)} className="text-muted hover:text-text text-xs">✕</button>
          </div>
          <pre className="p-3 font-mono text-[10px] text-text leading-relaxed whitespace-pre-wrap break-all">
            {status.last_log}
          </pre>
        </div>
      )}
    </div>
  );
}
