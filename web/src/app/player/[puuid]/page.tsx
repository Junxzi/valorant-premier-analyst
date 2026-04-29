import React from "react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AgentBadge } from "@/components/AgentBadge";
import { PlayerBio } from "@/components/PlayerBio";
import { AvatarUpload } from "@/components/AvatarUpload";
import { Card } from "@/components/Card";
import { resultPill } from "@/components/Pill";
import { VodCell } from "@/components/VodCell";
import { ApiError, fetchPlayer } from "@/lib/api";
import {
  formatGameStart,
  formatNumber,
  formatPercent,
  formatScore,
  playerDisplayName,
  teamDisplayName,
} from "@/lib/format";
import type {
  PlayerAgentStat,
  PlayerMapStat,
  PlayerMatchEntry,
  PlayerSummary,
  PlayerTeamAffiliation,
} from "@/lib/api";

type PageProps = {
  params: Promise<{ puuid: string }>;
};

export default async function PlayerPage({ params }: PageProps) {
  const { puuid: rawPuuid } = await params;
  const puuid = decodeURIComponent(rawPuuid);

  let data;
  try {
    data = await fetchPlayer(puuid, 30);
  } catch (e) {
    if (e instanceof ApiError && e.kind === "not_found") notFound();
    if (e instanceof ApiError && e.kind === "network") {
      return <BackendDown message={e.message} />;
    }
    throw e;
  }

  const playerLabel = playerDisplayName(data.name, data.tag, data.puuid);
  const isAnonymized = !data.name?.trim() && !data.tag?.trim();

  return (
    <div className="mx-auto max-w-6xl px-6 py-8 space-y-6">
      <PlayerHeader
        playerLabel={playerLabel}
        anonymized={isAnonymized}
        puuid={data.puuid}
        currentTeam={data.current_team}
        bio={<PlayerBio puuid={data.puuid} playerLabel={playerLabel} />}
      />
      {data.teams.length > 1 && <TeamAffiliations rows={data.teams} />}
      <AgentsDetailTable rows={data.agents} totalGames={data.summary.games} />
      <MapStats rows={data.maps} />
      <RecentMatches matches={data.recent_matches} />
    </div>
  );
}

function PlayerHeader({
  playerLabel,
  anonymized,
  puuid,
  currentTeam,
  bio,
}: {
  playerLabel: string;
  anonymized: boolean;
  puuid: string;
  currentTeam: PlayerTeamAffiliation | null;
  bio?: React.ReactNode;
}) {
  return (
    <section className="rounded-md border border-border bg-panel px-6 py-5">
      <div className="flex items-start gap-4">
        <AvatarUpload puuid={puuid} name={playerLabel} size={72} />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h1
              className={`text-3xl font-semibold tracking-tight ${
                anonymized ? "italic text-muted-strong" : "text-text-strong"
              }`}
              title={puuid}
            >
              {playerLabel}
            </h1>
          </div>
          {currentTeam ? (
            <p className="mt-1 text-sm text-muted">
              Current team:{" "}
              {currentTeam.premier_team_name && currentTeam.premier_team_tag ? (
                <Link
                  href={`/team/${encodeURIComponent(
                    currentTeam.premier_team_name,
                  )}/${encodeURIComponent(currentTeam.premier_team_tag)}`}
                  className="font-medium text-text hover:text-accent"
                >
                  {currentTeam.premier_team_name}
                  <span className="ml-1 text-muted">#{currentTeam.premier_team_tag}</span>
                </Link>
              ) : (
                <span className="text-muted">Unknown team</span>
              )}
              {"  -  "}
              <span className="tabular-nums">
                {currentTeam.games}G {currentTeam.wins}W
              </span>
            </p>
          ) : (
            <p className="mt-1 text-sm text-muted">No Premier team affiliation found.</p>
          )}
          {bio}
        </div>
      </div>
    </section>
  );
}

function SummaryRow({ summary }: { summary: PlayerSummary }) {
  const tiles = [
    { label: "Games", value: String(summary.games) },
    {
      label: "Winrate",
      value: formatPercent(summary.winrate_pct, 1),
      tone:
        summary.winrate_pct >= 50
          ? ("win" as const)
          : summary.games > 0
            ? ("loss" as const)
            : undefined,
    },
    { label: "Avg ACS", value: formatNumber(summary.avg_acs, 0) },
    {
      label: "K/D",
      value: formatNumber(summary.kd_ratio, 2),
      tone:
        summary.kd_ratio == null
          ? undefined
          : summary.kd_ratio >= 1
            ? ("win" as const)
            : ("loss" as const),
    },
    { label: "Avg ADR", value: formatNumber(summary.avg_adr, 0) },
    {
      label: "+/-",
      value:
        summary.avg_plus_minus == null
          ? "-"
          : `${summary.avg_plus_minus > 0 ? "+" : ""}${summary.avg_plus_minus.toFixed(1)}`,
      tone:
        summary.avg_plus_minus == null
          ? undefined
          : summary.avg_plus_minus > 0
            ? ("win" as const)
            : summary.avg_plus_minus < 0
              ? ("loss" as const)
              : undefined,
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {tiles.map((t) => (
        <div
          key={t.label}
          className="rounded-md border border-border bg-panel px-4 py-3"
        >
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">
            {t.label}
          </p>
          <p
            className={`mt-1 text-2xl font-semibold tabular-nums ${
              t.tone === "win"
                ? "text-win"
                : t.tone === "loss"
                  ? "text-loss"
                  : "text-text-strong"
            }`}
          >
            {t.value}
          </p>
        </div>
      ))}
    </div>
  );
}

function RecentMatches({ matches }: { matches: PlayerMatchEntry[] }) {
  return (
    <Card title={`Recent Matches (${matches.length})`} flush>
      {matches.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted">No match data found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-[11px] uppercase tracking-wider text-muted">
              <tr className="border-b border-border">
                <Th className="w-12">Res</Th>
                <Th className="w-20">Score</Th>
                <Th>Opponent</Th>
                <Th className="w-28">Map</Th>
                <Th className="w-28">Agent</Th>
                <Th className="w-14 text-right">K</Th>
                <Th className="w-14 text-right">D</Th>
                <Th className="w-14 text-right">A</Th>
                <Th className="w-16 text-right">ACS</Th>
                <Th className="w-14 text-right">VOD</Th>
                <Th className="w-36">Date</Th>
              </tr>
            </thead>
            <tbody>
              {matches.map((m) => (
                <PlayerMatchRow key={m.match_id} match={m} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function PlayerMatchRow({ match }: { match: PlayerMatchEntry }) {
  const opponentLabel = teamDisplayName(
    match.opponent_name,
    match.opponent_tag,
    null,
  );
  const href = `/match/${encodeURIComponent(match.match_id)}`;

  return (
    <tr className="group border-b border-border/60 transition-colors hover:bg-panel-hover">
      <LinkTd href={href}>{resultPill(match.has_won)}</LinkTd>
      <LinkTd href={href}>
        <span className="font-mono tabular-nums text-text-strong">
          {formatScore(match.rounds_won, match.rounds_lost)}
        </span>
      </LinkTd>
      <LinkTd href={href}>
        <span className="text-text group-hover:text-text-strong">
          {opponentLabel}
        </span>
      </LinkTd>
      <LinkTd href={href} className="text-muted-strong">
        {match.map_name ?? "-"}
      </LinkTd>
      <LinkTd href={href}>
        <AgentBadge agent={match.agent} size={22} />
      </LinkTd>
      <LinkTd href={href} className="text-right tabular-nums text-text">
        {match.kills ?? "-"}
      </LinkTd>
      <LinkTd href={href} className="text-right tabular-nums text-text">
        {match.deaths ?? "-"}
      </LinkTd>
      <LinkTd href={href} className="text-right tabular-nums text-text">
        {match.assists ?? "-"}
      </LinkTd>
      <LinkTd
        href={href}
        className="text-right tabular-nums font-medium text-text-strong"
      >
        {formatNumber(match.acs, 0)}
      </LinkTd>
      <td className="px-4 py-2.5 text-right align-middle">
        <VodCell url={match.vod_url} />
      </td>
      <LinkTd href={href} className="text-muted tabular-nums">
        {formatGameStart(match.game_start)}
      </LinkTd>
    </tr>
  );
}

function TeamAffiliations({ rows }: { rows: PlayerTeamAffiliation[] }) {
  return (
    <Card title="Team History" flush>
      {rows.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted">No team affiliations found.</p>
      ) : (
        <ul className="divide-y divide-border/60">
          {rows.map((t, idx) => {
            const linkable = Boolean(t.premier_team_name && t.premier_team_tag);
            const inner = (
              <div className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="font-medium text-text group-hover:text-accent">
                    {t.premier_team_name ?? "Unknown team"}
                  </p>
                  <p className="text-xs text-muted">
                    {t.premier_team_tag ? `#${t.premier_team_tag}` : ""}
                  </p>
                </div>
                <div className="text-right tabular-nums">
                  <p className="text-sm text-text-strong">
                    {t.games}G &middot;{" "}
                    <span className="text-win">{t.wins}W</span>
                    {" - "}
                    <span className="text-loss">{t.games - t.wins}L</span>
                  </p>
                  <p className="text-[11px] text-muted">
                    {formatPercent(
                      t.games ? (t.wins / t.games) * 100 : 0,
                      0,
                    )}
                  </p>
                </div>
              </div>
            );
            return (
              <li key={t.premier_team_id ?? `unknown-${idx}`} className="group">
                {linkable ? (
                  <Link
                    href={`/team/${encodeURIComponent(t.premier_team_name!)}/${encodeURIComponent(t.premier_team_tag!)}`}
                    className="block transition-colors hover:bg-panel-hover"
                  >
                    {inner}
                  </Link>
                ) : (
                  inner
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

function MapStats({ rows }: { rows: PlayerMapStat[] }) {
  return (
    <Card title="Map Stats" flush>
      {rows.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted">No map data found.</p>
      ) : (
        <table className="min-w-full text-sm">
          <thead className="text-[11px] uppercase tracking-wider text-muted">
            <tr className="border-b border-border">
              <Th>Map</Th>
              <Th className="w-14 text-right">Games</Th>
              <Th className="w-20">Win %</Th>
              <Th className="w-16 text-right">ACS</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.map_name ?? "unknown"}
                className="border-b border-border/60"
              >
                <Td className="font-medium text-text">{r.map_name ?? "Unknown"}</Td>
                <Td className="text-right tabular-nums text-muted-strong">
                  {r.games}
                </Td>
                <Td>
                  <WinrateBar value={r.winrate_pct} games={r.games} />
                </Td>
                <Td className="text-right tabular-nums text-muted-strong">
                  {formatNumber(r.avg_acs, 0)}
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

function AgentsDetailTable({
  rows,
  totalGames,
}: {
  rows: PlayerAgentStat[];
  totalGames: number;
}) {
  const cols: {
    key: string;
    label: string;
    tip?: string;
    highlight?: boolean;
  }[] = [
    { key: "use", label: "USE", tip: "Usage rate (games / total games)" },
    { key: "rnd", label: "RND", tip: "Rounds played" },
    { key: "acs", label: "ACS", tip: "Average Combat Score", highlight: true },
    { key: "kd", label: "K:D", tip: "Kill / Death ratio", highlight: true },
    { key: "adr", label: "ADR", tip: "Average Damage / Round" },
    { key: "kast", label: "KAST", tip: "Kill/Assist/Survive/Trade rate" },
    { key: "kpr", label: "KPR", tip: "Kills / Round" },
    { key: "apr", label: "APR", tip: "Assists / Round" },
    { key: "fkpr", label: "FKPR", tip: "First Kills / Round" },
    { key: "fdpr", label: "FDPR", tip: "First Deaths / Round" },
    { key: "k", label: "K", tip: "Total kills" },
    { key: "d", label: "D", tip: "Total deaths" },
    { key: "a", label: "A", tip: "Total assists" },
    { key: "fk", label: "FK", tip: "Total first kills" },
    { key: "fd", label: "FD", tip: "Total first deaths" },
  ];

  return (
    <Card title="AGENTS" flush>
      {rows.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted">No agent data found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-bg-elevated">
                <th className="w-px px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted" />
                {cols.map((c) => (
                  <th
                    key={c.key}
                    title={c.tip}
                    className={`px-3 py-2.5 text-right text-[11px] font-semibold uppercase tracking-wider ${
                      c.highlight ? "text-accent" : "text-muted"
                    }`}
                  >
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, idx) => {
                const kdTone =
                  r.kd_ratio == null
                    ? ""
                    : r.kd_ratio >= 1
                      ? "text-win"
                      : "text-loss";
                const usePct = totalGames > 0
                  ? Math.round((r.games / totalGames) * 100)
                  : 0;
                return (
                  <tr
                    key={r.agent ?? `unknown-${idx}`}
                    className="border-b border-border/60 transition-colors hover:bg-panel-hover"
                  >
                    <Td>
                      <AgentBadge agent={r.agent} size={28} showName={false} />
                    </Td>
                    <Td className="text-right tabular-nums text-text-strong font-medium">
                      <span className="text-muted mr-1.5">({r.games})</span>{usePct}%
                    </Td>
                    <Td className="text-right tabular-nums text-muted-strong">
                      {r.rounds}
                    </Td>
                    <Td className="text-right tabular-nums font-semibold text-text-strong">
                      {formatNumber(r.avg_acs, 1)}
                    </Td>
                    <Td className={`text-right tabular-nums font-semibold ${kdTone || "text-text-strong"}`}>
                      {formatNumber(r.kd_ratio, 2)}
                    </Td>
                    <Td className="text-right tabular-nums text-muted-strong">
                      {formatNumber(r.avg_adr, 1)}
                    </Td>
                    <Td className="text-right tabular-nums text-muted-strong">
                      {r.kast_pct != null ? `${formatNumber(r.kast_pct, 0)}%` : "—"}
                    </Td>
                    <Td className="text-right tabular-nums text-text">
                      {formatNumber(r.kpr, 2)}
                    </Td>
                    <Td className="text-right tabular-nums text-text">
                      {formatNumber(r.apr, 2)}
                    </Td>
                    <Td className="text-right tabular-nums text-text">
                      {formatNumber(r.fkpr, 2)}
                    </Td>
                    <Td className="text-right tabular-nums text-text">
                      {formatNumber(r.fdpr, 2)}
                    </Td>
                    <Td className="text-right tabular-nums text-text">
                      {r.total_kills}
                    </Td>
                    <Td className="text-right tabular-nums text-text">
                      {r.total_deaths}
                    </Td>
                    <Td className="text-right tabular-nums text-text">
                      {r.total_assists}
                    </Td>
                    <Td className="text-right tabular-nums text-text">
                      {r.total_first_kills}
                    </Td>
                    <Td className="text-right tabular-nums text-text">
                      {r.total_first_deaths}
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function WinrateBar({ value, games }: { value: number; games: number }) {
  if (games === 0) return <span className="text-muted">-</span>;
  const tone = value >= 50 ? "bg-win" : "bg-loss";
  const text = value >= 50 ? "text-win" : "text-loss";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg-elevated">
        <div
          className={`h-full ${tone}`}
          style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
        />
      </div>
      <span className={`w-10 shrink-0 text-right text-xs tabular-nums ${text}`}>
        {formatPercent(value, 0)}
      </span>
    </div>
  );
}

function LinkTd({
  href,
  children,
  className = "",
}: {
  href: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <td className="p-0 align-middle">
      <Link href={href} className={`block px-3 py-2.5 ${className}`}>
        {children}
      </Link>
    </td>
  );
}

function Th({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <th className={`px-3 py-2 text-left font-semibold ${className}`}>{children}</th>
  );
}

function Td({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <td className={`px-3 py-2.5 align-middle ${className}`}>{children}</td>;
}

function BackendDown({ message }: { message: string }) {
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <div className="rounded-md border border-loss/40 bg-loss-soft p-6">
        <h2 className="text-lg font-semibold text-loss">Backend unreachable</h2>
        <p className="mt-2 text-sm text-text">
          Could not connect to the FastAPI backend. Make sure the server is running.
        </p>
        <pre className="mt-3 overflow-x-auto rounded bg-bg-elevated p-3 text-xs text-muted-strong">
{`# From the project root:
.venv\\Scripts\\activate
valorant-analyst-server`}
        </pre>
        <p className="mt-3 text-xs text-muted">{message}</p>
        <Link
          href="/"
          className="mt-4 inline-flex items-center gap-1 text-sm text-accent hover:text-accent-strong"
        >
          Back to Home
        </Link>
      </div>
    </div>
  );
}
