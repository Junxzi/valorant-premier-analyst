"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Card } from "@/components/Card";
import type { RecentMatch } from "@/lib/api";
import { formatScore } from "@/lib/format";
import { mapThumbnailUrl } from "@/lib/maps";
import {
  buildWeekRows,
  isInPlayoff,
  summarizeSeason,
  V26A3,
  type Season,
  type WeekRow,
  type WeeklyMatchWithId,
} from "@/lib/seasons";

type Props = {
  matches: RecentMatch[];
};

const WEEKDAY_FORMAT: Intl.DateTimeFormatOptions = {
  timeZone: "Asia/Tokyo",
  month: "numeric",
  day: "numeric",
  weekday: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
};

export function PlayoffStatus({ matches }: Props) {
  const season: Season = V26A3;

  // Re-tick once per minute so the "current/scheduled/missed" labels and
  // the playoff countdown stay accurate without a hard reload.
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));
  useEffect(() => {
    const tick = () => setNow(Math.floor(Date.now() / 1000));
    const handle = setInterval(tick, 60_000);
    return () => clearInterval(handle);
  }, []);

  const weeklyInputs: WeeklyMatchWithId[] = useMemo(
    () =>
      matches.map((m) => ({
        match_id: m.match_id,
        game_start: m.game_start,
        has_won: m.our_team.has_won,
        rounds_won: m.our_team.rounds_won,
        rounds_lost: m.our_team.rounds_lost,
      })),
    [matches],
  );

  const summary = useMemo(
    () => summarizeSeason(season, weeklyInputs),
    [season, weeklyInputs],
  );

  const weekRows = useMemo(
    () => buildWeekRows(season, weeklyInputs, now),
    [season, weeklyInputs, now],
  );

  const playoffMatches = useMemo(
    () => matches.filter((m) => isInPlayoff(season, m.game_start)),
    [matches, season],
  );

  const winrate =
    summary.weeklyPlayed > 0
      ? Math.round((summary.weeklyWins / summary.weeklyPlayed) * 1000) / 10
      : null;

  return (
    <div className="space-y-6">
      <ScoreSummaryCard season={season} summary={summary} now={now} />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <TiebreakerTile
          label="Total Matches Played"
          value={String(summary.weeklyPlayed)}
          hint="ポイント同点時の第二指標"
        />
        <TiebreakerTile
          label="Round Differential"
          value={summary.roundDifferential >= 0
            ? `+${summary.roundDifferential}`
            : String(summary.roundDifferential)}
          hint={`Σ(rounds_won) − Σ(rounds_lost): ${summary.roundsWon} − ${summary.roundsLost}`}
        />
        <TiebreakerTile
          label="Win Rate"
          value={winrate == null ? "—" : `${winrate}%`}
          hint={`${summary.weeklyWins}W – ${summary.weeklyLosses}L`}
        />
      </div>

      <WeeklyTimelineCard rows={weekRows} now={now} />

      {playoffMatches.length > 0 && (
        <PlayoffMatchesCard matches={playoffMatches} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Top: Premier Score progress + remaining
// ---------------------------------------------------------------------------

function ScoreSummaryCard({
  season,
  summary,
  now,
}: {
  season: Season;
  summary: ReturnType<typeof summarizeSeason>;
  now: number;
}) {
  const playoffStartMs = season.playoffStartUnixSec * 1000;
  const daysToPlayoffs = Math.max(
    0,
    Math.ceil((playoffStartMs - now * 1000) / (24 * 3600 * 1000)),
  );
  const maxScore = season.weeklyMaxMatches * season.pointsPerWin;
  const currentPct = (summary.premierScore / maxScore) * 100;
  const reachablePct = (summary.maxPossibleScore / maxScore) * 100;

  return (
    <Card title={`${season.label} · Premier Score`} flush>
      <div className="px-6 py-5 space-y-5">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <div className="flex items-baseline gap-2">
            <span className="text-5xl font-bold tabular-nums text-text-strong">
              {summary.premierScore}
            </span>
            <span className="text-lg text-muted">/ {maxScore} pt</span>
          </div>
          <span className="text-sm text-muted">
            （残り {summary.weeklyRemaining} weekly · 最大 +{summary.maxRemainingPoints} pt）
          </span>
        </div>

        {/* Stacked progress bar:
              solid accent = points already earned
              soft accent  = points still reachable (= remaining matches × 100)
              empty        = points already foreclosed (matches lost) */}
        <div className="relative h-3 rounded-full bg-bg-elevated overflow-hidden">
          <div
            className="absolute inset-y-0 left-0 bg-accent/30"
            style={{ width: `${Math.min(100, reachablePct)}%` }}
            title={`Max possible: ${summary.maxPossibleScore} pt`}
          />
          <div
            className="absolute inset-y-0 left-0 bg-accent"
            style={{ width: `${Math.min(100, currentPct)}%` }}
            title={`Current: ${summary.premierScore} pt`}
          />
        </div>
        <div className="flex items-center justify-between text-[11px] text-muted tabular-nums">
          <span>0</span>
          <span>{Math.round(maxScore / 2)}</span>
          <span>{maxScore}</span>
        </div>

        <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-muted">
          <span>
            <span className="inline-block w-2 h-2 rounded-full bg-accent mr-1.5 align-middle" />
            獲得済み: <span className="text-text">{summary.premierScore} pt</span>
          </span>
          <span>
            <span className="inline-block w-2 h-2 rounded-full bg-accent/30 mr-1.5 align-middle" />
            残り獲得可能: <span className="text-text">{summary.maxRemainingPoints} pt</span>
          </span>
          <span className="ml-auto text-muted-strong">
            プレイオフ開始まで {daysToPlayoffs} 日
          </span>
        </div>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Tiebreaker tiles
// ---------------------------------------------------------------------------

function TiebreakerTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-md border border-border bg-panel px-4 py-3">
      <p className="text-[10px] uppercase tracking-widest text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-text-strong">
        {value}
      </p>
      {hint && <p className="mt-0.5 text-[11px] text-muted/70">{hint}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Week-by-week timeline (the most useful visualization)
// ---------------------------------------------------------------------------

function WeeklyTimelineCard({
  rows,
  now,
}: {
  rows: WeekRow[];
  now: number;
}) {
  return (
    <Card title="Weekly Schedule" flush>
      <div className="divide-y divide-border/60">
        {rows.map((row) => (
          <WeekRowView key={row.week.week} row={row} now={now} />
        ))}
      </div>
    </Card>
  );
}

function WeekRowView({ row, now }: { row: WeekRow; now: number }) {
  const thumb = mapThumbnailUrl(row.week.map);
  const dateLabel = new Date(row.week.game1UnixSec * 1000).toLocaleDateString(
    "ja-JP",
    { timeZone: "Asia/Tokyo", month: "numeric", day: "numeric", weekday: "short" },
  );

  return (
    <div className="grid grid-cols-1 md:grid-cols-[180px_1fr_1fr] items-center gap-4 px-5 py-3">
      <div className="flex items-center gap-3">
        <span className="text-[10px] uppercase tracking-widest text-muted/60 w-12">
          W{String(row.week.week).padStart(2, "0")}
        </span>
        {thumb && (
          <Image
            src={thumb}
            alt={row.week.map}
            width={48}
            height={28}
            className="rounded-sm object-cover opacity-80 shrink-0"
          />
        )}
        <div>
          <p className="text-sm font-semibold text-text-strong">{row.week.map}</p>
          <p className="text-[10px] text-muted tabular-nums">{dateLabel}</p>
        </div>
      </div>

      <SlotCell
        label="Game 1"
        slot={row.game1}
        slotUnixSec={row.week.game1UnixSec}
        now={now}
      />
      <SlotCell
        label="Game 2"
        slot={row.game2}
        slotUnixSec={row.week.game2UnixSec}
        now={now}
      />
    </div>
  );
}

function SlotCell({
  label,
  slot,
  slotUnixSec,
  now,
}: {
  label: string;
  slot: WeekRow["game1"];
  slotUnixSec: number;
  now: number;
}) {
  const time = new Date(slotUnixSec * 1000).toLocaleString("ja-JP", WEEKDAY_FORMAT);
  const inner = (() => {
    if (slot.kind === "win") {
      return (
        <span className="flex items-center gap-2">
          <span className="rounded-sm bg-win/20 text-win px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider">
            +100
          </span>
          <span className="font-mono tabular-nums text-text-strong text-sm">
            {formatScore(slot.rounds_won, slot.rounds_lost)}
          </span>
        </span>
      );
    }
    if (slot.kind === "loss") {
      return (
        <span className="flex items-center gap-2">
          <span className="rounded-sm bg-loss/20 text-loss px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider">
            +0
          </span>
          <span className="font-mono tabular-nums text-muted text-sm">
            {formatScore(slot.rounds_won, slot.rounds_lost)}
          </span>
        </span>
      );
    }
    if (slot.kind === "scheduled") {
      const deltaSec = slotUnixSec - now;
      const days = Math.floor(deltaSec / 86400);
      const hours = Math.floor((deltaSec % 86400) / 3600);
      const countdown = days > 0 ? `in ${days}d ${hours}h` : `in ${hours}h`;
      return (
        <span className="flex items-center gap-2 text-muted">
          <span className="text-[10px] uppercase tracking-wider">Scheduled</span>
          <span className="text-[11px] tabular-nums">{countdown}</span>
        </span>
      );
    }
    if (slot.kind === "current") {
      return (
        <span className="flex items-center gap-2 text-amber-400">
          <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          <span className="text-[10px] uppercase tracking-wider">Result Pending</span>
        </span>
      );
    }
    return (
      <span className="text-[10px] uppercase tracking-wider text-muted/40">
        No Match
      </span>
    );
  })();

  const matchHref =
    (slot.kind === "win" || slot.kind === "loss") && slot.matchId
      ? `/match/${encodeURIComponent(slot.matchId)}`
      : null;

  const body = (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-widest text-muted/60">
        {label} · <span className="tabular-nums">{time}</span>
      </span>
      {inner}
    </div>
  );

  if (matchHref) {
    return (
      <Link
        href={matchHref}
        className="rounded-md border border-border/60 bg-bg-elevated/40 px-3 py-2 hover:border-accent/60 transition-colors"
      >
        {body}
      </Link>
    );
  }
  return (
    <div className="rounded-md border border-border/60 bg-bg-elevated/40 px-3 py-2">
      {body}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Playoff matches (when they exist)
// ---------------------------------------------------------------------------

function PlayoffMatchesCard({ matches }: { matches: RecentMatch[] }) {
  return (
    <Card title="Playoffs (no points awarded)" flush>
      <ul className="divide-y divide-border/60">
        {matches.map((m) => (
          <li key={m.match_id} className="px-5 py-3 flex items-center gap-4">
            <span className="text-[11px] uppercase tracking-wider text-muted-strong w-16">
              {m.our_team.has_won === true
                ? "WIN"
                : m.our_team.has_won === false
                  ? "LOSS"
                  : "—"}
            </span>
            <span className="font-mono tabular-nums text-sm text-text-strong w-20">
              {formatScore(m.our_team.rounds_won, m.our_team.rounds_lost)}
            </span>
            <span className="text-sm text-text">
              {m.opponent.name ? `${m.opponent.name}#${m.opponent.tag ?? ""}` : "—"}
            </span>
            <span className="ml-auto text-xs text-muted">{m.map_name ?? "—"}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

