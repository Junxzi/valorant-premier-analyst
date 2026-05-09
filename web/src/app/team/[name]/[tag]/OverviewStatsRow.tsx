"use client";

import { useMemo } from "react";

import { SeasonToggle } from "@/components/SeasonToggle";
import type { RecentMatch, TeamRecord } from "@/lib/api";
import { formatPercent } from "@/lib/format";
import { filterMatchesBySeason } from "@/lib/seasons";
import { useSeasonQuery } from "@/lib/useSeasonQuery";

type Props = {
  /** Overall (all-time) record straight from the API. */
  overallRecord: TeamRecord;
  /** Full match list — used to derive per-season aggregates. */
  matches: RecentMatch[];
};

/**
 * Hero stats row on the team Overview page.
 *
 * Defaults to the current season (V26A3 = "from the most recent Ascent
 * match onwards") because that's what the user is actively tracking; a
 * toggle lets them flip back to the all-time / 全体 view when needed.
 */
export function OverviewStatsRow({ overallRecord, matches }: Props) {
  const { season, setSeason } = useSeasonQuery();

  const seasonRecord = useMemo<TeamRecord>(() => {
    if (season === "all") return overallRecord;

    let wins = 0;
    let losses = 0;
    for (const m of filterMatchesBySeason(matches, season)) {
      if (m.our_team.has_won === true) wins += 1;
      else if (m.our_team.has_won === false) losses += 1;
    }
    const games = wins + losses;
    const winrate_pct = games > 0 ? (wins / games) * 100 : 0;
    return { games, wins, losses, winrate_pct };
  }, [season, matches, overallRecord]);

  const heading =
    season === "all" ? "全体 Record" : `${season.toUpperCase()} Record`;

  const tiles = [
    { label: "Games", value: String(seasonRecord.games) },
    {
      label: "Wins",
      value: String(seasonRecord.wins),
      tone: "win" as const,
    },
    {
      label: "Losses",
      value: String(seasonRecord.losses),
      tone: "loss" as const,
    },
    {
      label: "Winrate",
      value: formatPercent(seasonRecord.winrate_pct),
      tone:
        seasonRecord.games === 0
          ? undefined
          : seasonRecord.winrate_pct >= 50
            ? ("win" as const)
            : ("loss" as const),
    },
  ];

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-strong">
          {heading}
        </h2>
        <SeasonToggle value={season} onChange={setSeason} />
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
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
    </section>
  );
}
