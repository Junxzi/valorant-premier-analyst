import Image from "next/image";
import { notFound } from "next/navigation";

import { Card } from "@/components/Card";
import { CurrentRoster } from "@/components/CurrentRoster";
import { ApiError, fetchTeam, fetchTeamMatches } from "@/lib/api";
import { mapThumbnailUrl } from "@/lib/maps";
import { getTeamStaff } from "@/lib/teamConfig";
import type {
  RecentMatch,
  UpcomingMatch,
} from "@/lib/api";

import { OverviewStatsRow } from "./OverviewStatsRow";
import { RecentMatchesCard } from "./RecentMatchesCard";

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

  // Fetch the team summary and the full match list concurrently. The full
  // match list backs both the season-filtered StatsRow tiles and the
  // RecentMatchesCard (whose visible rows depend on the toggle).
  let data;
  let allMatches: RecentMatch[];
  try {
    const [teamData, matchesData] = await Promise.all([
      fetchTeam(name, tag, 1),
      fetchTeamMatches(name, tag),
    ]);
    data = teamData;
    allMatches = matchesData.matches;
  } catch (e) {
    if (e instanceof ApiError && e.kind === "not_found") notFound();
    throw e;
  }

  const matchesHref = `/team/${encodeURIComponent(name)}/${encodeURIComponent(
    tag,
  )}/matches`;
  const { ongoing, upcoming } = categorizeSchedule(
    allMatches.map((m) => m.game_start),
  );

  return (
    <div className="space-y-6">
      <OverviewStatsRow overallRecord={data.record} matches={allMatches} />
      {ongoing.length > 0 && <OngoingMatches matches={ongoing} />}
      {upcoming.length > 0 && <UpcomingMatches matches={upcoming} />}
      <RecentMatchesCard
        matches={allMatches}
        visibleLimit={RECENT_LIMIT}
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

