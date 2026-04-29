"use client";

import { useCallback, useEffect, useState } from "react";

import { Card } from "@/components/Card";
import { ApiError, fetchVods, saveVods } from "@/lib/api";

type Row = {
  rid: string;
  match_id: string;
  url: string;
};

function newRow(): Row {
  return {
    rid:
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `r-${Math.random().toString(36).slice(2)}`,
    match_id: "",
    url: "",
  };
}

function rowsFromUrls(urls: Record<string, string>): Row[] {
  return Object.entries(urls)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([match_id, url]) => ({
      rid:
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `r-${match_id.slice(0, 8)}`,
      match_id,
      url,
    }));
}

export default function VodSettingsPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchVods()
      .then((d) => {
        if (!cancelled) setRows(rowsFromUrls(d.urls));
      })
      .catch((e) => {
        if (!cancelled) {
          setError(
            e instanceof ApiError
              ? e.message
              : e instanceof Error
                ? e.message
                : "読み込みに失敗しました。",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const patchRow = useCallback((rid: string, field: keyof Pick<Row, "match_id" | "url">, value: string) => {
    setRows((prev) =>
      prev.map((r) => (r.rid === rid ? { ...r, [field]: value } : r)),
    );
  }, []);

  const removeRow = useCallback((rid: string) => {
    setRows((prev) => prev.filter((r) => r.rid !== rid));
  }, []);

  const addRow = useCallback(() => {
    setRows((prev) => [...prev, newRow()]);
  }, []);

  const handleSave = useCallback(async () => {
    setError(null);
    setSaved(false);

    const out: Record<string, string> = {};
    const seenDup = new Set<string>();

    for (const r of rows) {
      const mid = r.match_id.trim();
      const u = r.url.trim();
      if (!mid && !u) continue;

      if (mid && seenDup.has(mid)) {
        setError(`重複した match_id があります: ${mid.slice(0, 12)}…`);
        return;
      }
      if (mid) seenDup.add(mid);

      if (!mid && u) {
        setError("URL だけ行があります。match_id（試合ページ URL の UUID）を入力してください。");
        return;
      }

      if (mid && !u) continue;

      if (mid && u) out[mid] = u;
    }

    setSaving(true);
    try {
      const savedData = await saveVods(out);
      setRows(rowsFromUrls(savedData.urls));
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "保存に失敗しました。",
      );
    } finally {
      setSaving(false);
    }
  }, [rows]);

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-6 py-8">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-text-strong">
          VOD の紐付け
        </h1>
        <p className="mt-1 max-w-xl text-sm text-muted">
          キーには試合一覧・試合詳細の URL に含まれる{" "}
          <span className="font-mono">match id</span>{" "}
          （UUID）をそのまま入れます。保存すると{" "}
          <code className="rounded bg-bg-elevated px-1 font-mono text-xs">data/vods.json</code>{" "}
          に書き込まれます。
        </p>
      </div>

      <Card
        title="URL 一覧"
        action={
          <div className="flex items-center gap-3">
            {saved && (
              <span className="text-[11px] font-semibold uppercase tracking-wider text-win">
                保存しました
              </span>
            )}
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || loading}
              className="rounded-md border border-border bg-bg-elevated px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-strong transition-colors hover:bg-panel-hover disabled:opacity-50"
            >
              {saving ? "保存中…" : "保存"}
            </button>
          </div>
        }
      >
        {error && (
          <p className="mb-4 rounded-md border border-loss/40 bg-loss/10 px-3 py-2 text-sm text-loss">
            {error}
          </p>
        )}

        {loading ? (
          <p className="text-sm text-muted">読み込み中…</p>
        ) : (
          <div className="space-y-3">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="text-[11px] uppercase tracking-wider text-muted">
                  <tr className="border-b border-border">
                    <th className="pb-2 pr-2 text-left font-semibold">match id</th>
                    <th className="pb-2 pr-2 text-left font-semibold">VOD URL</th>
                    <th className="w-14 pb-2 text-right font-semibold"> </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="py-6 text-muted">
                        まだ登録がありません。「行を追加」から入力してください。
                      </td>
                    </tr>
                  ) : (
                    rows.map((r) => (
                      <tr key={r.rid} className="border-b border-border/50">
                        <td className="py-2 pr-2 align-top">
                          <input
                            type="text"
                            value={r.match_id}
                            onChange={(e) => patchRow(r.rid, "match_id", e.target.value)}
                            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                            className="w-full min-w-[240px] rounded border border-border bg-bg px-2 py-1.5 font-mono text-xs text-text placeholder:text-muted"
                            spellCheck={false}
                            autoCapitalize="off"
                            autoCorrect="off"
                          />
                        </td>
                        <td className="py-2 pr-2 align-top">
                          <input
                            type="url"
                            value={r.url}
                            onChange={(e) => patchRow(r.rid, "url", e.target.value)}
                            placeholder="https://youtube.com/… または Twitch など"
                            className="w-full min-w-[280px] rounded border border-border bg-bg px-2 py-1.5 font-mono text-xs text-text placeholder:text-muted"
                            spellCheck={false}
                          />
                        </td>
                        <td className="py-2 text-right align-top">
                          <button
                            type="button"
                            onClick={() => removeRow(r.rid)}
                            className="text-[11px] font-semibold uppercase tracking-wider text-muted hover:text-loss"
                          >
                            削除
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <button
              type="button"
              onClick={addRow}
              className="text-[11px] font-semibold uppercase tracking-wider text-accent hover:underline"
            >
              + 行を追加
            </button>

            <p className="text-xs text-muted">
              HTTP(S) の URL のみ保存できます。
              URL を空にして保存すると、その match id のリンクはサイト全体から取り除かれます。
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}
