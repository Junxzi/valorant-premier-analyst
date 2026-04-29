import { notFound } from "next/navigation";
import Image from "next/image";

import { Tabs } from "@/components/Tabs";
import { ApiError, fetchTeam } from "@/lib/api";
import { getTeamIcon } from "@/lib/teamConfig";
import { formatPercent } from "@/lib/format";

type Props = {
  params: Promise<{ name: string; tag: string }>;
  children: React.ReactNode;
};

/**
 * Shared chrome for the three team tabs (Overview / Matches / Stats).
 *
 * The layout fetches the lightweight team record so the header stays in
 * sync across tabs without each page having to re-render it. Tab pages
 * fetch their own detailed data on top.
 */
export default async function TeamLayout({ params, children }: Props) {
  const { name: rawName, tag: rawTag } = await params;
  const name = decodeURIComponent(rawName);
  const tag = decodeURIComponent(rawTag);

  let record;
  try {
    const team = await fetchTeam(name, tag, 1);
    record = team.record;
  } catch (e) {
    if (e instanceof ApiError) {
      if (e.kind === "not_found") notFound();
      if (e.kind === "network") return <BackendDown message={e.message} />;
    }
    throw e;
  }

  const base = `/team/${encodeURIComponent(name)}/${encodeURIComponent(tag)}`;
  const teamIcon = getTeamIcon(name, tag);
  const tabs = [
    { id: "overview", label: "Overview", href: base },
    { id: "stats", label: "Stats", href: `${base}/stats` },
    { id: "matches", label: "Matches", href: `${base}/matches` },
    { id: "strategy", label: "Strategy", href: `${base}/strategy` },
  ];

  return (
    <div className="mx-auto max-w-6xl px-6 py-8 space-y-6">
      <section className="rounded-md border border-border bg-panel px-6 py-5">
        <p className="text-xs uppercase tracking-widest text-muted">Premier Team</p>
        <div className="mt-1 flex items-center gap-4">
          {teamIcon && (
            <Image
              src={teamIcon}
              alt={`${name} icon`}
              width={56}
              height={56}
              className="rounded-md object-contain"
            />
          )}
          <div>
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h1 className="text-3xl font-semibold tracking-tight text-text-strong">
                {name}
              </h1>
              <span className="text-lg font-medium text-muted">#{tag}</span>
            </div>
            <p className="mt-1 text-sm text-muted tabular-nums">
              {record.games} games · {record.wins}W – {record.losses}L
              {record.games > 0 && (
                <span className="ml-2 text-muted-strong">
                  ({formatPercent(record.winrate_pct, 1)})
                </span>
              )}
            </p>
          </div>
        </div>
      </section>

      <Tabs tabs={tabs} />

      {children}
    </div>
  );
}

function BackendDown({ message }: { message: string }) {
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <div className="rounded-md border border-loss/40 bg-loss-soft p-6">
        <h2 className="text-lg font-semibold text-loss">Backend unreachable</h2>
        <p className="mt-2 text-sm text-text">
          バックエンド API に接続できませんでした。FastAPI サーバが起動しているか確認してください。
        </p>
        <pre className="mt-3 overflow-x-auto rounded bg-bg-elevated p-3 text-xs text-muted-strong">
{`# プロジェクトルートで:
.venv\\Scripts\\activate
valorant-analyst-server`}
        </pre>
        <p className="mt-3 text-xs text-muted">{message}</p>
      </div>
    </div>
  );
}
