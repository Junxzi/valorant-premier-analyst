"use client";

import { useMemo } from "react";

import type { RecentMatch, TeamRecord } from "@/lib/api";
import { formatPercent } from "@/lib/format";
import { filterMatchesBySeason } from "@/lib/seasons";
import { useSeasonQuery } from "@/lib/useSeasonQuery";

type Props = {
  overallRecord: TeamRecord;
  matches: RecentMatch[];
};

/**
 * The "{games} games · {wins}W – {losses}L ({winrate})" line under the team
 * name in the shared team layout. Reads `?season=` from the URL so it stays
 * in sync with the OverviewStatsRow toggle and the Matches tab.
 */
export function TeamHeaderRecord({ overallRecord, matches }: Props) {
  const { season } = useSeasonQuery();

  const record = useMemo<TeamRecord>(() => {
    if (season === "all") return overallRecord;
    let wins = 0;
    let losses = 0;
    for (const m of filterMatchesBySeason(matches, season)) {
      if (m.our_team.has_won === true) wins += 1;
      else if (m.our_team.has_won === false) losses += 1;
    }
    const games = wins + losses;
    return {
      games,
      wins,
      losses,
      winrate_pct: games > 0 ? (wins / games) * 100 : 0,
    };
  }, [season, matches, overallRecord]);

  const seasonBadge =
    season === "all" ? null : (
      <span className="ml-2 rounded-sm bg-bg-elevated px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-strong">
        {season.toUpperCase()}
      </span>
    );

  return (
    <p className="mt-1 text-sm text-muted tabular-nums">
      {record.games} games · {record.wins}W – {record.losses}L
      {record.games > 0 && (
        <span className="ml-2 text-muted-strong">
          ({formatPercent(record.winrate_pct, 1)})
        </span>
      )}
      {seasonBadge}
    </p>
  );
}
