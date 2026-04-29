"""Pydantic response models — these define the public API contract.

The frontend mirrors these as TypeScript types.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    db_present: bool
    db_path: str


class TeamRecord(BaseModel):
    games: int
    wins: int
    losses: int
    winrate_pct: float


class OurTeamSummary(BaseModel):
    team: str = Field(description="Red or Blue.")
    rounds_won: int | None
    rounds_lost: int | None
    has_won: bool | None


class OpponentSummary(BaseModel):
    team: str | None
    name: str | None
    tag: str | None
    rounds_won: int | None
    rounds_lost: int | None


class RecentMatch(BaseModel):
    match_id: str
    vod_url: str | None = None
    map_name: str | None
    mode: str | None
    queue: str | None
    game_start: int | None
    our_team: OurTeamSummary
    opponent: OpponentSummary


class MapWinrate(BaseModel):
    map_name: str | None
    games: int
    wins: int
    winrate_pct: float


class RosterMember(BaseModel):
    puuid: str
    name: str | None
    tag: str | None
    games: int
    avg_kills: float | None
    avg_deaths: float | None
    kd_ratio: float | None
    agent_main: str | None


class UpcomingMatch(BaseModel):
    """A scheduled future match. Populated from the premier_schedule table."""

    scheduled_at: int = Field(description="Unix timestamp (seconds) of the match start.")
    map_name: str | None = None
    opponent_name: str | None = None
    opponent_tag: str | None = None


class TeamResponse(BaseModel):
    name: str
    tag: str
    record: TeamRecord
    upcoming_matches: list[UpcomingMatch] = Field(default_factory=list)
    recent_matches: list[RecentMatch]
    map_winrates: list[MapWinrate]
    roster: list[RosterMember]


# ----------------------------- match detail -----------------------------


class MatchTeamSummary(BaseModel):
    """A single side (Red or Blue) of a match."""

    team: str = Field(description="Red or Blue.")
    has_won: bool | None
    rounds_won: int | None
    rounds_lost: int | None
    premier_team_id: str | None
    premier_team_name: str | None
    premier_team_tag: str | None


class RoundEntry(BaseModel):
    round_num: int
    winning_team: str | None
    end_type: str | None = Field(
        description="Free-form HenrikDev label, e.g. 'Bomb defused', 'Eliminated'.",
    )
    bomb_planted: bool | None
    bomb_defused: bool | None


class MatchPlayerStat(BaseModel):
    """Per-player stats for a single match.

    ``acs`` and ``adr`` are derived (score / total_rounds and damage / total_rounds)
    so the frontend doesn't have to know the round count.
    """

    puuid: str
    name: str | None
    tag: str | None
    team: str | None
    agent: str | None
    kills: int | None
    deaths: int | None
    assists: int | None
    score: int | None
    damage_made: int | None
    damage_received: int | None
    acs: float | None
    adr: float | None
    kd_ratio: float | None
    plus_minus: int | None


class MatchDetail(BaseModel):
    match_id: str
    vod_url: str | None = None
    map_name: str | None
    mode: str | None
    queue: str | None
    game_start: int | None
    game_length: int | None
    total_rounds: int = Field(description="Sum of rounds_won across both teams.")
    teams: list[MatchTeamSummary]
    rounds: list[RoundEntry]
    players: list[MatchPlayerStat]


class RoundEconomyEntry(BaseModel):
    round_num: int
    team: str
    total_loadout: int
    avg_loadout: float
    total_spent: int
    player_count: int


# ----------------------------- team: matches list -----------------------------


class TeamMatchListResponse(BaseModel):
    """Full chronological match list for a team's `Matches` tab."""

    name: str
    tag: str
    total: int
    matches: list[RecentMatch]


# ----------------------------- team: stats tab -----------------------------


class TeamPlayerStat(BaseModel):
    """Per-player aggregated stats for the team's `Stats` tab.

    Extends ``RosterMember`` with derived per-round metrics (ACS / ADR) and
    +/- so the frontend can render a vlr.gg-style player stats table.
    """

    puuid: str
    name: str | None
    tag: str | None
    games: int
    rounds: int = Field(description="Sum of rounds the player took part in.")
    avg_kills: float | None
    avg_deaths: float | None
    avg_assists: float | None
    avg_acs: float | None = Field(description="Combat score per round, averaged.")
    avg_adr: float | None = Field(description="Damage per round, averaged.")
    avg_plus_minus: float | None
    kd_ratio: float | None
    agent_main: str | None


class TeamAgentUsage(BaseModel):
    """How often a given agent shows up on the team."""

    agent: str | None
    games: int
    pick_rate_pct: float = Field(
        description="games / team_games * 100. Sum across agents can exceed 100% "
        "because 5 picks per match.",
    )
    avg_acs: float | None
    avg_adr: float | None


class TeamStatsResponse(BaseModel):
    name: str
    tag: str
    total_games: int
    total_rounds: int
    players: list[TeamPlayerStat]
    agent_usage: list[TeamAgentUsage]


# ----------------------------- team: map-stats tab -----------------------------


class TeamMapAgentComp(BaseModel):
    """One agent composition (sorted agent list) used on a map."""

    agents: list[str]
    count: int


class TeamMapMatchDetail(BaseModel):
    """Single match result used in the expanded map row."""

    match_id: str
    vod_url: str | None = None
    game_start: int | None
    has_won: bool | None
    rounds_won: int | None
    rounds_lost: int | None
    opponent_name: str | None
    opponent_tag: str | None
    atk_first: bool
    atk_rounds_won: int
    atk_rounds_lost: int
    def_rounds_won: int
    def_rounds_lost: int
    agents: list[str]


class TeamMapStat(BaseModel):
    map_name: str | None
    games: int
    wins: int
    losses: int
    winrate_pct: float
    # ATK side round stats
    atk_rounds_won: int
    atk_rounds_lost: int
    atk_rw_pct: float
    # DEF side round stats
    def_rounds_won: int
    def_rounds_lost: int
    def_rw_pct: float
    # Maps where we started on ATK side first half
    atk_first_games: int
    atk_first_wins: int
    atk_first_winrate_pct: float
    # Maps where we started on DEF side first half
    def_first_games: int
    def_first_wins: int
    def_first_winrate_pct: float
    # Top agent compositions used on this map
    agent_comps: list[TeamMapAgentComp]
    # Per-match detail for the expanded row
    matches: list[TeamMapMatchDetail]


class TeamMapStatsResponse(BaseModel):
    name: str
    tag: str
    maps: list[TeamMapStat]


# ----------------------------- player overview -----------------------------


class PlayerTeamAffiliation(BaseModel):
    """A Premier team the player has appeared with."""

    premier_team_id: str | None
    premier_team_name: str | None
    premier_team_tag: str | None
    games: int
    wins: int
    first_seen: int | None = Field(
        description="Earliest game_start (raw HenrikDev value) for this team.",
    )
    last_seen: int | None


class PlayerAgentStat(BaseModel):
    agent: str | None
    games: int
    rounds: int
    use_pct: float
    avg_kills: float | None
    avg_deaths: float | None
    avg_assists: float | None
    avg_acs: float | None
    avg_adr: float | None
    kd_ratio: float | None
    kpr: float | None
    apr: float | None
    fkpr: float | None
    fdpr: float | None
    kast_pct: float | None = Field(
        description="Kill/Assist/Survive/Trade rate as a percentage.",
    )
    total_kills: int
    total_deaths: int
    total_assists: int
    total_first_kills: int
    total_first_deaths: int


class PlayerMapStat(BaseModel):
    map_name: str | None
    games: int
    wins: int
    winrate_pct: float
    avg_acs: float | None
    avg_adr: float | None


class PlayerMatchEntry(BaseModel):
    """A single match the player participated in."""

    match_id: str
    vod_url: str | None = None
    map_name: str | None
    game_start: int | None
    team: str | None = Field(description="Red/Blue side the player was on.")
    has_won: bool | None
    rounds_won: int | None
    rounds_lost: int | None
    premier_team_name: str | None
    premier_team_tag: str | None
    opponent_name: str | None
    opponent_tag: str | None
    agent: str | None
    kills: int | None
    deaths: int | None
    assists: int | None
    acs: float | None
    adr: float | None
    plus_minus: int | None


class PlayerSummary(BaseModel):
    games: int
    wins: int
    losses: int
    winrate_pct: float
    rounds: int
    avg_kills: float | None
    avg_deaths: float | None
    avg_assists: float | None
    avg_acs: float | None
    avg_adr: float | None
    avg_plus_minus: float | None
    kd_ratio: float | None
    agent_main: str | None


class PlayerOverview(BaseModel):
    puuid: str
    name: str | None
    tag: str | None
    current_team: PlayerTeamAffiliation | None = Field(
        description="The team the player was on in their most recent match.",
    )
    summary: PlayerSummary
    teams: list[PlayerTeamAffiliation]
    agents: list[PlayerAgentStat]
    maps: list[PlayerMapStat]
    recent_matches: list[PlayerMatchEntry]
