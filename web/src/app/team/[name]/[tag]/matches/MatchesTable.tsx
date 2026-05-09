"use client";

import Link from "next/link";
import { useMemo } from "react";

import { Card } from "@/components/Card";
import { resultPill } from "@/components/Pill";
import { SeasonToggle } from "@/components/SeasonToggle";
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
  matches: RecentMatch[];
  totalAll: number;
};

export function MatchesTable({ matches, totalAll }: Props) {
  const { season, setSeason } = useSeasonQuery();

  const visible = useMemo(
    () => filterMatchesBySeason(matches, season),
    [matches, season],
  );

  const wins = visible.filter((m) => m.our_team.has_won === true).length;
  const losses = visible.filter((m) => m.our_team.has_won === false).length;

  const titleCount = season === "all" ? totalAll : visible.length;
  const seasonLabel = season === "all" ? "" : ` · ${season.toUpperCase()}`;

  return (
    <div className="space-y-6">
      <Card
        title={`All Matches (${titleCount})${seasonLabel}`}
        action={
          <div className="flex items-center gap-3">
            <span className="text-[11px] tabular-nums text-muted">
              <span className="text-win">{wins}W</span>
              {" – "}
              <span className="text-loss">{losses}L</span>
            </span>
            <SeasonToggle value={season} onChange={setSeason} />
          </div>
        }
        flush
      >
        {visible.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted">
            {season === "all"
              ? "まだ試合データがありません。"
              : `${season.toUpperCase()} の試合はまだありません。`}
          </p>
        ) : (
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
                  <MatchRow key={m.match_id} match={m} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function MatchRow({ match }: { match: RecentMatch }) {
  const opponentLabel = teamDisplayName(
    match.opponent.name,
    match.opponent.tag,
    match.opponent.team,
  );
  const href = `/match/${encodeURIComponent(match.match_id)}`;

  return (
    <tr className="group border-b border-border/60 transition-colors hover:bg-panel-hover">
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
    <th className={`px-4 py-2 text-left font-semibold ${className}`}>{children}</th>
  );
}
