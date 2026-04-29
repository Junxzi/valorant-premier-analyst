/**
 * Typed client for the FastAPI backend.
 *
 * Types here mirror `src/valorant_analyst/server/schemas.py` 1:1.
 * If you change the Pydantic models, update these too (or generate them).
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

/** Seconds to cache GET responses on the Next.js server (production only). 0 = still cache no-store. */
const API_GET_REVALIDATE_SEC = Number(process.env.API_REVALIDATE_SECONDS ?? "30");


export type HealthResponse = {
  status: string;
  db_present: boolean;
  db_path: string;
};

export type TeamRecord = {
  games: number;
  wins: number;
  losses: number;
  winrate_pct: number;
};

export type OurTeamSummary = {
  team: string;
  rounds_won: number | null;
  rounds_lost: number | null;
  has_won: boolean | null;
};

export type OpponentSummary = {
  team: string | null;
  name: string | null;
  tag: string | null;
  rounds_won: number | null;
  rounds_lost: number | null;
};

export type RecentMatch = {
  match_id: string;
  map_name: string | null;
  mode: string | null;
  queue: string | null;
  game_start: number | null;
  our_team: OurTeamSummary;
  opponent: OpponentSummary;
};

export type MapWinrate = {
  map_name: string | null;
  games: number;
  wins: number;
  winrate_pct: number;
};

export type RosterMember = {
  puuid: string;
  name: string | null;
  tag: string | null;
  games: number;
  avg_kills: number | null;
  avg_deaths: number | null;
  kd_ratio: number | null;
  agent_main: string | null;
};

export type UpcomingMatch = {
  scheduled_at: number;
  map_name: string | null;
  opponent_name: string | null;
  opponent_tag: string | null;
};

export type TeamResponse = {
  name: string;
  tag: string;
  record: TeamRecord;
  upcoming_matches: UpcomingMatch[];
  recent_matches: RecentMatch[];
  map_winrates: MapWinrate[];
  roster: RosterMember[];
};

/* ---------- match detail ---------- */

export type MatchTeamSummary = {
  team: string;
  has_won: boolean | null;
  rounds_won: number | null;
  rounds_lost: number | null;
  premier_team_id: string | null;
  premier_team_name: string | null;
  premier_team_tag: string | null;
};

export type RoundEntry = {
  round_num: number;
  winning_team: string | null;
  end_type: string | null;
  bomb_planted: boolean | null;
  bomb_defused: boolean | null;
};

export type MatchPlayerStat = {
  puuid: string;
  name: string | null;
  tag: string | null;
  team: string | null;
  agent: string | null;
  kills: number | null;
  deaths: number | null;
  assists: number | null;
  score: number | null;
  damage_made: number | null;
  damage_received: number | null;
  acs: number | null;
  adr: number | null;
  kd_ratio: number | null;
  plus_minus: number | null;
};

export type MatchDetail = {
  match_id: string;
  map_name: string | null;
  mode: string | null;
  queue: string | null;
  game_start: number | null;
  game_length: number | null;
  total_rounds: number;
  teams: MatchTeamSummary[];
  rounds: RoundEntry[];
  players: MatchPlayerStat[];
};

/* ---------- team: matches tab ---------- */

export type TeamMatchListResponse = {
  name: string;
  tag: string;
  total: number;
  matches: RecentMatch[];
};

/* ---------- team: stats tab ---------- */

export type TeamPlayerStat = {
  puuid: string;
  name: string | null;
  tag: string | null;
  games: number;
  rounds: number;
  avg_kills: number | null;
  avg_deaths: number | null;
  avg_assists: number | null;
  avg_acs: number | null;
  avg_adr: number | null;
  avg_plus_minus: number | null;
  kd_ratio: number | null;
  agent_main: string | null;
};

export type TeamAgentUsage = {
  agent: string | null;
  games: number;
  pick_rate_pct: number;
  avg_acs: number | null;
  avg_adr: number | null;
};

export type TeamStatsResponse = {
  name: string;
  tag: string;
  total_games: number;
  total_rounds: number;
  players: TeamPlayerStat[];
  agent_usage: TeamAgentUsage[];
};

/* ---------- team: map-stats tab ---------- */

export type TeamMapAgentComp = {
  agents: string[];
  count: number;
};

export type TeamMapMatchDetail = {
  match_id: string;
  game_start: number | null;
  has_won: boolean | null;
  rounds_won: number | null;
  rounds_lost: number | null;
  opponent_name: string | null;
  opponent_tag: string | null;
  atk_first: boolean;
  atk_rounds_won: number;
  atk_rounds_lost: number;
  def_rounds_won: number;
  def_rounds_lost: number;
  agents: string[];
};

export type TeamMapStat = {
  map_name: string | null;
  games: number;
  wins: number;
  losses: number;
  winrate_pct: number;
  atk_rounds_won: number;
  atk_rounds_lost: number;
  atk_rw_pct: number;
  def_rounds_won: number;
  def_rounds_lost: number;
  def_rw_pct: number;
  atk_first_games: number;
  atk_first_wins: number;
  atk_first_winrate_pct: number;
  def_first_games: number;
  def_first_wins: number;
  def_first_winrate_pct: number;
  agent_comps: TeamMapAgentComp[];
  matches: TeamMapMatchDetail[];
};

export type TeamMapStatsResponse = {
  name: string;
  tag: string;
  maps: TeamMapStat[];
};

/* ---------- player overview ---------- */

export type PlayerTeamAffiliation = {
  premier_team_id: string | null;
  premier_team_name: string | null;
  premier_team_tag: string | null;
  games: number;
  wins: number;
  first_seen: number | null;
  last_seen: number | null;
};

export type PlayerAgentStat = {
  agent: string | null;
  games: number;
  rounds: number;
  use_pct: number;
  avg_kills: number | null;
  avg_deaths: number | null;
  avg_assists: number | null;
  avg_acs: number | null;
  avg_adr: number | null;
  kd_ratio: number | null;
  kpr: number | null;
  apr: number | null;
  kast_pct: number | null;
  fkpr: number | null;
  fdpr: number | null;
  total_kills: number;
  total_deaths: number;
  total_assists: number;
  total_first_kills: number;
  total_first_deaths: number;
};

export type PlayerMapStat = {
  map_name: string | null;
  games: number;
  wins: number;
  winrate_pct: number;
  avg_acs: number | null;
  avg_adr: number | null;
};

export type PlayerMatchEntry = {
  match_id: string;
  map_name: string | null;
  game_start: number | null;
  team: string | null;
  has_won: boolean | null;
  rounds_won: number | null;
  rounds_lost: number | null;
  premier_team_name: string | null;
  premier_team_tag: string | null;
  opponent_name: string | null;
  opponent_tag: string | null;
  agent: string | null;
  kills: number | null;
  deaths: number | null;
  assists: number | null;
  acs: number | null;
  adr: number | null;
  plus_minus: number | null;
};

export type PlayerSummary = {
  games: number;
  wins: number;
  losses: number;
  winrate_pct: number;
  rounds: number;
  avg_kills: number | null;
  avg_deaths: number | null;
  avg_assists: number | null;
  avg_acs: number | null;
  avg_adr: number | null;
  avg_plus_minus: number | null;
  kd_ratio: number | null;
  agent_main: string | null;
};

export type PlayerOverview = {
  puuid: string;
  name: string | null;
  tag: string | null;
  current_team: PlayerTeamAffiliation | null;
  summary: PlayerSummary;
  teams: PlayerTeamAffiliation[];
  agents: PlayerAgentStat[];
  maps: PlayerMapStat[];
  recent_matches: PlayerMatchEntry[];
};

export class ApiError extends Error {
  status: number;
  kind: "not_found" | "network" | "http";
  constructor(kind: ApiError["kind"], message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  let res: Response;
  const method = init?.method?.toUpperCase() ?? "GET";
  const isGet = method === "GET";
  const cacheOptions =
    isGet &&
    process.env.NODE_ENV === "production" &&
    API_GET_REVALIDATE_SEC > 0
      ? { next: { revalidate: API_GET_REVALIDATE_SEC } as const }
      : { cache: "no-store" as const };

  try {
    res = await fetch(url, {
      ...init,
      ...cacheOptions,
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    throw new ApiError(
      "network",
      `Could not reach the API at ${API_BASE_URL}: ${msg}. Is \`valorant-analyst-server\` running?`,
    );
  }
  if (!res.ok) {
    if (res.status === 404) {
      throw new ApiError("not_found", `Not found: ${path}`, 404);
    }
    let detail = "";
    try {
      const body = (await res.json()) as { detail?: string };
      detail = body?.detail ?? "";
    } catch {
      // ignore JSON parse failures
    }
    throw new ApiError(
      "http",
      `API ${res.status} on ${path}${detail ? `: ${detail}` : ""}`,
      res.status,
    );
  }
  return (await res.json()) as T;
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export function fetchTeam(
  name: string,
  tag: string,
  recentLimit = 10,
): Promise<TeamResponse> {
  const path = `/api/teams/${encodeURIComponent(name)}/${encodeURIComponent(
    tag,
  )}?recent_limit=${recentLimit}`;
  return request<TeamResponse>(path);
}

export function fetchMatch(matchId: string): Promise<MatchDetail> {
  return request<MatchDetail>(`/api/matches/${encodeURIComponent(matchId)}`);
}

export type RoundEconomyEntry = {
  round_num: number;
  team: string;
  total_loadout: number;
  avg_loadout: number;
  total_spent: number;
  player_count: number;
};

export function fetchMatchEconomy(matchId: string): Promise<RoundEconomyEntry[]> {
  return request<RoundEconomyEntry[]>(
    `/api/matches/${encodeURIComponent(matchId)}/economy`,
  );
}

// { map name → { player name → agent name | null } }
export type StrategyData = Record<string, Record<string, string | null>>;

export function fetchTeamStrategy(name: string, tag: string): Promise<{ data: StrategyData }> {
  return request<{ data: StrategyData }>(
    `/api/teams/${encodeURIComponent(name)}/${encodeURIComponent(tag)}/strategy`,
  );
}

export function saveTeamStrategy(
  name: string,
  tag: string,
  data: StrategyData,
): Promise<{ data: StrategyData }> {
  return request<{ data: StrategyData }>(
    `/api/teams/${encodeURIComponent(name)}/${encodeURIComponent(tag)}/strategy`,
    { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ data }) },
  );
}

export function fetchTeamMatches(
  name: string,
  tag: string,
  limit?: number,
): Promise<TeamMatchListResponse> {
  const qs = limit ? `?limit=${limit}` : "";
  return request<TeamMatchListResponse>(
    `/api/teams/${encodeURIComponent(name)}/${encodeURIComponent(tag)}/matches${qs}`,
  );
}

export function fetchTeamStats(
  name: string,
  tag: string,
): Promise<TeamStatsResponse> {
  return request<TeamStatsResponse>(
    `/api/teams/${encodeURIComponent(name)}/${encodeURIComponent(tag)}/stats`,
  );
}

export function fetchTeamMapStats(
  name: string,
  tag: string,
): Promise<TeamMapStatsResponse> {
  return request<TeamMapStatsResponse>(
    `/api/teams/${encodeURIComponent(name)}/${encodeURIComponent(tag)}/map-stats`,
  );
}

export function fetchPlayer(
  puuid: string,
  recentLimit = 20,
): Promise<PlayerOverview> {
  return request<PlayerOverview>(
    `/api/players/${encodeURIComponent(puuid)}?recent_limit=${recentLimit}`,
  );
}
