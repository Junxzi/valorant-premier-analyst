import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Card } from "@/components/Card";
import { CurrentRoster } from "@/components/CurrentRoster";
import { resultPill } from "@/components/Pill";
import { VodCell } from "@/components/VodCell";
import { ApiError, fetchTeam } from "@/lib/api";
import { mapThumbnailUrl } from "@/lib/maps";
import { getTeamStaff } from "@/lib/teamConfig";
import {
  formatGameStart,
  formatPercent,
  formatScore,
  teamDisplayName,
} from "@/lib/format";
import type {
  RecentMatch,
  TeamRecord,
  UpcomingMatch,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// V26A3 schedule — fixed, computed from start date
// ---------------------------------------------------------------------------

const V26A3_SCHEDULE_MAPS = ["Ascent", "Lotus", "Breeze", "Pearl", "Haven", "Fracture"];

/** May 9 2026 20:00 JST (UTC+9) = May 9 11:00 UTC */
const WEEK1_GAME1_UTC_MS = Date.UTC(2026, 4, 9, 11, 0, 0);

function buildFullSchedule(): UpcomingMatch[] {
  const schedule: UpcomingMatch[] = [];
  const WEEK_MS = 7 * 24 * 60 * 60 * 1000;
  const TWO_HOURS_MS = 2 * 60 * 60 * 1000;
  for (let week = 0; week < V26A3_SCHEDULE_MAPS.length; week++) {
    const mapName = V26A3_SCHEDULE_MAPS[week];
    const g1 = WEEK1_GAME1_UTC_MS + week * WEEK_MS;
    schedule.push({ scheduled_at: g1 / 1000, map_name: mapName, opponent_name: null, opponent_tag: null });
    schedule.push({ scheduled_at: (g1 + TWO_HOURS_MS) / 1000, map_name: mapName, opponent_name: null, opponent_tag: null });
  }
  return schedule;
}

/** 4 hours — covers match duration + possible API delay */
const RESULT_TOLERANCE_SEC = 4 * 3600;

function categorizeSchedule(
  recentGameStarts: (number | null)[],
): { ongoing: UpcomingMatch[]; upcoming: UpcomingMatch[] } {
  const nowSec = Date.now() / 1000;
  const knownTimestamps = recentGameStarts.filter((t): t is number => t !== null);

  const ongoing: UpcomingMatch[] = [];
  const upcoming: UpcomingMatch[] = [];

  for (const m of buildFullSchedule()) {
    if (m.scheduled_at > nowSec) {
      upcoming.push(m);
    } else {
      const hasResult = knownTimestamps.some(
        (t) => Math.abs(t - m.scheduled_at) < RESULT_TOLERANCE_SEC,
      );
      if (!hasResult) ongoing.push(m);
    }
  }

  return { ongoing, upcoming: upcoming.slice(0, 2) };
}

type PageProps = {
  params: Promise<{ name: string; tag: string }>;
};

export default async function TeamOverviewPage({ params }: PageProps) {
  const { name: rawName, tag: rawTag } = await params;
  const name = decodeURIComponent(rawName);
  const tag = decodeURIComponent(rawTag);

  const RECENT_LIMIT = 5;

  let data;
  try {
    data = await fetchTeam(name, tag, RECENT_LIMIT);
  } catch (e) {
    if (e instanceof ApiError && e.kind === "not_found") notFound();
    throw e;
  }

  const matchesHref = `/team/${encodeURIComponent(name)}/${encodeURIComponent(
    tag,
  )}/matches`;
  const moreCount = Math.max(0, data.record.games - data.recent_matches.length);
  const { ongoing, upcoming } = categorizeSchedule(
    data.recent_matches.map((m) => m.game_start),
  );

  return (
    <div className="space-y-6">
      <StatsRow record={data.record} />
      {ongoing.length > 0 && <OngoingMatches matches={ongoing} />}
      {upcoming.length > 0 && <UpcomingMatches matches={upcoming} />}
      <RecentMatches
        matches={data.recent_matches}
        moreCount={moreCount}
        moreHref={matchesHref}
      />
      <CurrentRoster members={data.roster} staff={getTeamStaff(name, tag)} />
    </div>
  );
}

function OngoingMatches({ matches }: { matches: UpcomingMatch[] }) {
  return (
    <Card title="Ongoing / Result Pending" flush>
      <div className="divide-y divide-border/60">
        {matches.map((m, i) => {
          const thumb = mapThumbnailUrl(m.map_name);
          const dateObj = new Date(m.scheduled_at * 1000);
          const dateLabel = dateObj.toLocaleString("ja-JP", {
            timeZone: "Asia/Tokyo",
            month: "numeric",
            day: "numeric",
            weekday: "short",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
          });
          return (
            <div key={i} className="flex items-center gap-4 px-5 py-4">
              {thumb ? (
                <Image src={thumb} alt={m.map_name ?? "Map"} width={72} height={40}
                  className="rounded-sm object-cover opacity-80 shrink-0" />
              ) : (
                <div className="w-[72px] h-10 rounded-sm bg-bg-elevated shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-text-strong">{m.map_name ?? "TBD"}</p>
                <p className="text-xs text-muted tabular-nums mt-0.5">{dateLabel} JST</p>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                <span className="text-xs font-semibold text-amber-400 uppercase tracking-wider">
                  Result Pending
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function UpcomingMatches({ matches }: { matches: UpcomingMatch[] }) {
  const now = Date.now() / 1000;
  return (
    <Card title="Upcoming Matches" flush>
      <div className="divide-y divide-border/60">
        {matches.map((m, i) => {
          const diffSec = Math.max(0, m.scheduled_at - now);
          const days = Math.floor(diffSec / 86400);
          const hours = Math.floor((diffSec % 86400) / 3600);
          const mins = Math.floor((diffSec % 3600) / 60);
          const countdown =
            days > 0 ? `${days}d ${hours}h` : hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;

          const thumb = mapThumbnailUrl(m.map_name);

          // Format date in JST
          const dateObj = new Date(m.scheduled_at * 1000);
          const dateLabel = dateObj.toLocaleString("ja-JP", {
            timeZone: "Asia/Tokyo",
            month: "numeric",
            day: "numeric",
            weekday: "short",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
          });

          return (
            <div key={i} className="flex items-center gap-4 px-5 py-4">
              {/* Map thumbnail */}
              {thumb ? (
                <Image
                  src={thumb}
                  alt={m.map_name ?? "Map"}
                  width={72}
                  height={40}
                  className="rounded-sm object-cover opacity-80 shrink-0"
                />
              ) : (
                <div className="w-[72px] h-10 rounded-sm bg-bg-elevated shrink-0" />
              )}

              {/* Map name */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-text-strong">
                  {m.map_name ?? "TBD"}
                </p>
                <p className="text-xs text-muted tabular-nums mt-0.5">{dateLabel} JST</p>
              </div>

              {/* Countdown */}
              <div className="text-right">
                <p className="text-lg font-bold tabular-nums text-accent">{countdown}</p>
                <p className="text-[10px] text-muted uppercase tracking-wider">remaining</p>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function StatsRow({ record }: { record: TeamRecord }) {
  const tiles = [
    { label: "Games", value: String(record.games) },
    { label: "Wins", value: String(record.wins), tone: "win" as const },
    { label: "Losses", value: String(record.losses), tone: "loss" as const },
    {
      label: "Winrate",
      value: formatPercent(record.winrate_pct),
      tone:
        record.winrate_pct >= 50
          ? ("win" as const)
          : record.games > 0
            ? ("loss" as const)
            : undefined,
    },
  ];
  return (
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
  );
}

function RecentMatches({
  matches,
  moreCount,
  moreHref,
}: {
  matches: RecentMatch[];
  moreCount: number;
  moreHref: string;
}) {
  return (
    <Card title="Recent Matches" flush>
      {matches.length === 0 ? (
        <EmptyState message="まだ試合データがありません。" />
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
                {matches.map((m) => (
                  <RecentMatchRow key={m.match_id} match={m} />
                ))}
              </tbody>
            </table>
          </div>
          {moreCount > 0 && (
            <Link
              href={moreHref}
              className="group flex items-center justify-center gap-2 border-t border-border px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-muted transition-colors hover:bg-panel-hover hover:text-accent"
            >
              <span>… {moreCount} more {moreCount === 1 ? "match" : "matches"}</span>
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

/**
 * Table cell that wraps its content in a `Link` so the entire row navigates
 * to the match detail page. Using a single `<Link>` per `<tr>` is invalid
 * HTML, so we put the link in every cell instead.
 */
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

function Td({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <td className={`px-4 py-2.5 align-middle ${className}`}>{children}</td>;
}

function EmptyState({ message }: { message: string }) {
  return <p className="px-4 py-6 text-sm text-muted">{message}</p>;
}
