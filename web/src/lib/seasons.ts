/**
 * Premier season definitions — single source of truth for weekly windows,
 * map rotation, and Premier Score math used by the Strategy / Matches /
 * Playoffs tabs.
 *
 * V26A3 schedule (Contender / Invite divisions, JST evening slot):
 *   Week 1  Ascent     May 9, 2026  20:00 + 22:00 JST
 *   Week 2  Lotus      May 16
 *   Week 3  Breeze     May 23
 *   Week 4  Pearl      May 30
 *   Week 5  Haven      June 6
 *   Week 6  Fracture   June 13
 *   Playoffs           June 20-21
 *
 * The user's team is in a Contender zone, so Week 7 (Split) is excluded.
 * Premier rules (Riot Support 42083235567251):
 *   - Weekly win = +100 points (a "Bye" also counts as a win)
 *   - Weekly loss = 0 points
 *   - Playoff matches do NOT award points
 *   - Tiebreakers: Premier Score -> Total Matches Played -> Round Differential
 */

const ONE_HOUR_MS = 60 * 60 * 1000;
const TWO_HOURS_MS = 2 * ONE_HOUR_MS;
const WEEK_MS = 7 * 24 * ONE_HOUR_MS;

/** May 9, 2026 11:00 UTC == May 9 20:00 JST (Week 1 game 1). */
const V26A3_WEEK1_GAME1_UTC_MS = Date.UTC(2026, 4, 9, 11, 0, 0);

const V26A3_MAPS: readonly string[] = [
  "Ascent",
  "Lotus",
  "Breeze",
  "Pearl",
  "Haven",
  "Fracture",
];

export type SeasonWeek = {
  week: number;
  map: string;
  game1UnixSec: number;
  game2UnixSec: number;
};

export type Season = {
  id: SeasonId;
  label: string;
  /** Unix sec window where weekly matches count toward Premier Score. */
  weeklyStartUnixSec: number;
  weeklyEndUnixSec: number;
  /** Playoff bracket window (matches here do NOT award points). */
  playoffStartUnixSec: number;
  playoffEndUnixSec: number;
  weeks: readonly SeasonWeek[];
  /** Maximum number of weekly matches in this season (= weeks.length * 2). */
  weeklyMaxMatches: number;
  pointsPerWin: number;
};

export type SeasonId = "v26a3";

/** A few hours of slack on either side so a slightly delayed match still counts. */
const MATCH_BUFFER_MS = 6 * ONE_HOUR_MS;

function buildV26A3Weeks(): SeasonWeek[] {
  return V26A3_MAPS.map((map, idx) => {
    const game1Ms = V26A3_WEEK1_GAME1_UTC_MS + idx * WEEK_MS;
    return {
      week: idx + 1,
      map,
      game1UnixSec: Math.floor(game1Ms / 1000),
      game2UnixSec: Math.floor((game1Ms + TWO_HOURS_MS) / 1000),
    };
  });
}

const V26A3_WEEKS = buildV26A3Weeks();
const V26A3_LAST_GAME_MS =
  V26A3_WEEK1_GAME1_UTC_MS + (V26A3_MAPS.length - 1) * WEEK_MS + TWO_HOURS_MS;

export const V26A3: Season = {
  id: "v26a3",
  label: "V26A3",
  weeklyStartUnixSec: Math.floor(
    (V26A3_WEEK1_GAME1_UTC_MS - MATCH_BUFFER_MS) / 1000,
  ),
  weeklyEndUnixSec: Math.floor((V26A3_LAST_GAME_MS + MATCH_BUFFER_MS) / 1000),
  playoffStartUnixSec: Math.floor(Date.UTC(2026, 5, 20, 0, 0, 0) / 1000),
  playoffEndUnixSec: Math.floor(Date.UTC(2026, 5, 22, 0, 0, 0) / 1000),
  weeks: V26A3_WEEKS,
  weeklyMaxMatches: V26A3_WEEKS.length * 2,
  pointsPerWin: 100,
};

export const SEASONS: readonly Season[] = [V26A3];

export function findSeasonById(id: SeasonId): Season | undefined {
  return SEASONS.find((s) => s.id === id);
}

// ---------------------------------------------------------------------------
// Generic season filtering — used by every "全体 / V26A3" toggle in the UI
// ---------------------------------------------------------------------------

/** Anything with a `game_start` we can dispatch on. */
type HasGameStart = { game_start: number | null | undefined };

/**
 * Return matches whose `game_start` falls within the given season's window
 * (weekly + playoffs). When `season === "all"` (or unknown) the input list
 * is returned as-is so callers can use a single code path.
 */
export function filterMatchesBySeason<T extends HasGameStart>(
  matches: readonly T[],
  season: "all" | SeasonId,
): T[] {
  if (season === "all") return [...matches];
  const def = findSeasonById(season);
  if (!def) return [...matches];
  return matches.filter(
    (m) =>
      isInWeekly(def, m.game_start ?? null) ||
      isInPlayoff(def, m.game_start ?? null),
  );
}

/**
 * Return the (since, until) Unix-second window for a season filter, or
 * `null` when no filter should be applied. Suitable to pass to backend
 * endpoints that accept `since` / `until` query params.
 */
export function seasonWindowUnixSec(
  season: "all" | SeasonId,
): { since: number; until: number } | null {
  if (season === "all") return null;
  const def = findSeasonById(season);
  if (!def) return null;
  return {
    since: def.weeklyStartUnixSec,
    // Stretch to playoff end so playoff matches stay included.
    until: def.playoffEndUnixSec,
  };
}

/**
 * True if *gameStartUnixSec* falls inside the season's weekly window. Used
 * to exclude scrims, customs, and playoff matches (which never award
 * points) from Premier Score math.
 */
export function isInWeekly(season: Season, gameStartUnixSec: number | null): boolean {
  if (gameStartUnixSec == null) return false;
  return (
    gameStartUnixSec >= season.weeklyStartUnixSec &&
    gameStartUnixSec <= season.weeklyEndUnixSec
  );
}

/** True if the match falls inside the playoff bracket window. */
export function isInPlayoff(season: Season, gameStartUnixSec: number | null): boolean {
  if (gameStartUnixSec == null) return false;
  return (
    gameStartUnixSec >= season.playoffStartUnixSec &&
    gameStartUnixSec <= season.playoffEndUnixSec
  );
}

/**
 * Map a match start time to its 1-indexed week number, or null if the
 * match is outside the weekly window. Picks the nearest scheduled slot
 * within +-12h to handle slight server-side timing drift.
 */
export function weekOfMatch(
  season: Season,
  gameStartUnixSec: number | null,
): number | null {
  if (gameStartUnixSec == null || !isInWeekly(season, gameStartUnixSec)) {
    return null;
  }
  const TOLERANCE_SEC = 12 * 3600;
  let best: { week: number; distance: number } | null = null;
  for (const w of season.weeks) {
    for (const slot of [w.game1UnixSec, w.game2UnixSec]) {
      const distance = Math.abs(gameStartUnixSec - slot);
      if (distance <= TOLERANCE_SEC && (best === null || distance < best.distance)) {
        best = { week: w.week, distance };
      }
    }
  }
  if (best) return best.week;
  // Fall back to "nearest week-start" if a match drifted outside the slot
  // tolerance but is still in the season window — better than dropping it.
  const week1Start = season.weeks[0].game1UnixSec;
  const idx = Math.floor((gameStartUnixSec - week1Start) / (7 * 24 * 3600));
  if (idx >= 0 && idx < season.weeks.length) return idx + 1;
  return null;
}

/**
 * One match's contribution to Premier Score / round differential. Matches
 * outside the weekly window contribute zero so the same shape can be
 * folded over an unfiltered list.
 */
export type WeeklyMatchInput = {
  game_start: number | null;
  has_won: boolean | null;
  rounds_won: number | null;
  rounds_lost: number | null;
};

export type SeasonSummary = {
  season: Season;
  weeklyWins: number;
  weeklyLosses: number;
  weeklyPlayed: number;
  weeklyRemaining: number;
  premierScore: number;
  maxRemainingPoints: number;
  maxPossibleScore: number;
  roundsWon: number;
  roundsLost: number;
  roundDifferential: number;
};

export function summarizeSeason(
  season: Season,
  matches: readonly WeeklyMatchInput[],
): SeasonSummary {
  let wins = 0;
  let losses = 0;
  let rw = 0;
  let rl = 0;
  for (const m of matches) {
    if (!isInWeekly(season, m.game_start)) continue;
    if (m.has_won === true) wins += 1;
    else if (m.has_won === false) losses += 1;
    if (typeof m.rounds_won === "number") rw += m.rounds_won;
    if (typeof m.rounds_lost === "number") rl += m.rounds_lost;
  }
  const played = wins + losses;
  const remaining = Math.max(0, season.weeklyMaxMatches - played);
  const score = wins * season.pointsPerWin;
  const maxRemaining = remaining * season.pointsPerWin;
  return {
    season,
    weeklyWins: wins,
    weeklyLosses: losses,
    weeklyPlayed: played,
    weeklyRemaining: remaining,
    premierScore: score,
    maxRemainingPoints: maxRemaining,
    maxPossibleScore: score + maxRemaining,
    roundsWon: rw,
    roundsLost: rl,
    roundDifferential: rw - rl,
  };
}

/** Map a list of weekly matches into the per-week schedule slots. */
export type WeeklySlotResult =
  | { kind: "win"; rounds_won: number | null; rounds_lost: number | null; matchId?: string }
  | { kind: "loss"; rounds_won: number | null; rounds_lost: number | null; matchId?: string }
  | { kind: "scheduled" }
  | { kind: "current" }
  | { kind: "missed" };

export type WeekRow = {
  week: SeasonWeek;
  game1: WeeklySlotResult;
  game2: WeeklySlotResult;
};

export type WeeklyMatchWithId = WeeklyMatchInput & { match_id?: string };

export function buildWeekRows(
  season: Season,
  matches: readonly WeeklyMatchWithId[],
  nowUnixSec: number = Math.floor(Date.now() / 1000),
): WeekRow[] {
  const TOLERANCE_SEC = 12 * 3600;

  function pickFor(slotSec: number): WeeklyMatchWithId | null {
    let best: { m: WeeklyMatchWithId; distance: number } | null = null;
    for (const m of matches) {
      if (m.game_start == null) continue;
      const distance = Math.abs(m.game_start - slotSec);
      if (distance <= TOLERANCE_SEC && (best === null || distance < best.distance)) {
        best = { m, distance };
      }
    }
    return best?.m ?? null;
  }

  function classify(slotSec: number): WeeklySlotResult {
    const m = pickFor(slotSec);
    if (m) {
      const kind = m.has_won === true ? "win" : "loss";
      return {
        kind,
        rounds_won: m.rounds_won ?? null,
        rounds_lost: m.rounds_lost ?? null,
        matchId: m.match_id,
      };
    }
    if (nowUnixSec < slotSec) return { kind: "scheduled" };
    if (nowUnixSec - slotSec < 4 * 3600) return { kind: "current" };
    return { kind: "missed" };
  }

  return season.weeks.map((week) => ({
    week,
    game1: classify(week.game1UnixSec),
    game2: classify(week.game2UnixSec),
  }));
}
