"use client";

import Link from "next/link";
import { useMemo } from "react";

import { Card } from "@/components/Card";
import { resultPill } from "@/components/Pill";
import { VodCell } from "@/components/VodCell";
import type { RecentMatch } from "@/lib/api";
import {
  formatGameStart,
  formatScore,
  teamDisplayName,
} from "@/lib/format";
import { filterMatchesBySeason } from "@/lib/seasons";
import { useSeasonQuery } from "@/lib/useSeasonQuery";

type Props = {
  /** Full match list — filtered client-side by the current `?season=` value. */
  matches: RecentMatch[];
  /** Maximum number of rows to show inline before the "… more" link. */
  visibleLimit: number;
  /** Where the "… more" link points (i.e. the team's `/matches` tab). */
  moreHref: string;
};

/**
 * Recent-matches card on the team Overview tab.
 *
 * Pulls the season filter from the shared `?season=` URL param via
 * `useSeasonQuery()` so it stays in sync with `OverviewStatsRow` and the
 * layout header. After filtering, shows the latest `visibleLimit` rows
 * with a "… N more" link to the full Matches tab.
 */
export function RecentMatchesCard({ matches, visibleLimit, moreHref }: Props) {
  const { season } = useSeasonQuery();

  const filtered = useMemo(
    () => filterMatchesBySeason(matches, season),
    [matches, season],
  );
  const visible = filtered.slice(0, visibleLimit);
  const moreCount = Math.max(0, filtered.length - visible.length);

  // Carry the active `?season=` over to the Matches tab so the user
  // doesn't lose their filter when they drill in.
  const moreHrefWithSeason =
    season === "v26a3"
      ? moreHref
      : `${moreHref}?season=${encodeURIComponent(season)}`;

  return (
    <Card title="Recent Matches" flush>
      {visible.length === 0 ? (
        <EmptyState
          message={
            season === "all"
              ? "まだ試合データがありません。"
              : `${season.toUpperCase()} の試合はまだありません。`
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-[11px] uppercase tracking-wider text-muted">
                <tr className="border-b border-border">
                  <Th className="w-14">Result</Th>
                  <Th className="w-24">Score</Th>
                  <Th>Opponent</Th>
                  <Th className="w-32">Map</Th>
                  <Th className="w-28">Mode</Th>
                  <Th className="w-44">Date</Th>
                  <Th className="w-20 text-right">VOD</Th>
                </tr>
              </thead>
              <tbody>
                {visible.map((m) => (
                  <RecentMatchRow key={m.match_id} match={m} />
                ))}
              </tbody>
            </table>
          </div>
          {moreCount > 0 && (
            <Link
              href={moreHrefWithSeason}
              className="group flex items-center justify-center gap-2 border-t border-border px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-muted transition-colors hover:bg-panel-hover hover:text-accent"
            >
              <span>
                … {moreCount} more {moreCount === 1 ? "match" : "matches"}
              </span>
              <span aria-hidden className="transition-transform group-hover:translate-x-0.5">
                →
              </span>
            </Link>
          )}
        </>
      )}
    </Card>
  );
}

function RecentMatchRow({ match }: { match: RecentMatch }) {
  const opponentLabel = teamDisplayName(
    match.opponent.name,
    match.opponent.tag,
    match.opponent.team,
  );
  const href = `/match/${encodeURIComponent(match.match_id)}`;

  return (
    <tr className="group cursor-pointer border-b border-border/60 transition-colors hover:bg-panel-hover">
      <LinkTd href={href}>{resultPill(match.our_team.has_won)}</LinkTd>
      <LinkTd href={href}>
        <span className="font-mono tabular-nums text-text-strong">
          {formatScore(match.our_team.rounds_won, match.our_team.rounds_lost)}
        </span>
      </LinkTd>
      <LinkTd href={href}>
        <span className="text-text group-hover:text-text-strong">
          {opponentLabel}
        </span>
      </LinkTd>
      <LinkTd href={href} className="text-muted-strong">
        {match.map_name ?? "—"}
      </LinkTd>
      <LinkTd href={href} className="text-muted">
        {match.queue ?? match.mode ?? "—"}
      </LinkTd>
      <LinkTd href={href} className="text-muted tabular-nums">
        {formatGameStart(match.game_start)}
      </LinkTd>
      <td className="px-4 py-2.5 text-right align-middle">
        <VodCell url={match.vod_url} />
      </td>
    </tr>
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
      <Link href={href} className={`block px-4 py-2.5 ${className}`}>
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
    <th className={`px-4 py-2 text-left font-semibold ${className}`}>
      {children}
    </th>
  );
}

function EmptyState({ message }: { message: string }) {
  return <p className="px-4 py-6 text-sm text-muted">{message}</p>;
}
