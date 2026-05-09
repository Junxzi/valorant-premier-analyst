"use client";

import { SeasonToggle } from "@/components/SeasonToggle";
import type { PlayerSummary } from "@/lib/api";
import { formatNumber, formatPercent } from "@/lib/format";
import { useSeasonQuery } from "@/lib/useSeasonQuery";

type Props = {
  /** Already filtered server-side per the active `?season=`. */
  summary: PlayerSummary;
};

/**
 * Hero summary row on the player page: 6 tiles (Games / Winrate /
 * Avg ACS / K/D / Avg ADR / +/-) plus the V26A3 ↔ 全体 toggle.
 *
 * Since this is the only toggle on the page, every other section
 * (agents, maps, recent matches, team affiliations) re-renders when
 * `?season=` flips because the server component above re-runs and
 * passes freshly-filtered data.
 */
export function PlayerSummaryRow({ summary }: Props) {
  const { season, setSeason } = useSeasonQuery();

  const tiles = [
    { label: "Games", value: String(summary.games) },
    {
      label: "Winrate",
      value: formatPercent(summary.winrate_pct, 1),
      tone:
        summary.games === 0
          ? undefined
          : summary.winrate_pct >= 50
            ? ("win" as const)
            : ("loss" as const),
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
          ? "—"
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

  const heading =
    season === "all" ? "全体 Stats" : `${season.toUpperCase()} Stats`;

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-strong">
          {heading}
        </h2>
        <SeasonToggle value={season} onChange={setSeason} />
      </div>
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
    </section>
  );
}
