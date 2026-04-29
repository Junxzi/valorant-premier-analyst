"""Basic scoreboard-style metrics over normalized DataFrames."""

from __future__ import annotations

import numpy as np
import pandas as pd

PLAYER_SUMMARY_COLUMNS: list[str] = [
    "name",
    "tag",
    "agent",
    "games",
    "avg_kills",
    "avg_deaths",
    "avg_assists",
    "avg_score",
    "kd_ratio",
]

MAP_SUMMARY_COLUMNS: list[str] = [
    "map_name",
    "games",
    "avg_match_length_min",
]


def player_summary(match_players: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-player averages across all observed matches.

    A player is identified by the (name, tag, agent) tuple so picking different
    agents shows up as separate rows -- useful when scouting a Premier roster.
    """
    if match_players is None or match_players.empty:
        return pd.DataFrame(columns=PLAYER_SUMMARY_COLUMNS)

    df = match_players.copy()
    for col in ("kills", "deaths", "assists", "score"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = pd.NA

    for col in ("name", "tag", "agent"):
        if col not in df.columns:
            df[col] = pd.NA

    grouped = (
        df.groupby(["name", "tag", "agent"], dropna=False)
        .agg(
            games=("kills", "size"),
            avg_kills=("kills", "mean"),
            avg_deaths=("deaths", "mean"),
            avg_assists=("assists", "mean"),
            avg_score=("score", "mean"),
            total_kills=("kills", "sum"),
            total_deaths=("deaths", "sum"),
        )
        .reset_index()
    )

    total_kills = pd.to_numeric(grouped["total_kills"], errors="coerce")
    total_deaths = pd.to_numeric(grouped["total_deaths"], errors="coerce")
    safe_deaths = total_deaths.where(total_deaths > 0, np.nan)
    grouped["kd_ratio"] = total_kills / safe_deaths

    for col in ("avg_kills", "avg_deaths", "avg_assists", "avg_score", "kd_ratio"):
        grouped[col] = pd.to_numeric(grouped[col], errors="coerce").round(2)

    grouped = grouped.sort_values(
        ["games", "avg_score"], ascending=[False, False], kind="stable"
    )

    return grouped[PLAYER_SUMMARY_COLUMNS].reset_index(drop=True)


def map_summary(
    matches: pd.DataFrame,
    match_players: pd.DataFrame,  # noqa: ARG001 -- reserved for future per-side stats
) -> pd.DataFrame:
    """Per-map aggregation.

    TODO: HenrikDev's v3 payload exposes round-by-round and per-team scores.
    Once we wire those through ``normalize.py``, this function should produce
    win-rate, attacker/defender splits, and pistol round metrics. For now we
    return the simplest "how often did we play this map" view so the report
    has something useful even before that work lands.
    """
    if matches is None or matches.empty:
        return pd.DataFrame(columns=MAP_SUMMARY_COLUMNS)

    df = matches.copy()
    if "map_name" not in df.columns:
        return pd.DataFrame(columns=MAP_SUMMARY_COLUMNS)

    if "game_length" in df.columns:
        df["game_length"] = pd.to_numeric(df["game_length"], errors="coerce")
    else:
        df["game_length"] = pd.NA

    grouped = (
        df.groupby("map_name", dropna=False)
        .agg(
            games=("match_id", "count"),
            avg_match_length_sec=("game_length", "mean"),
        )
        .reset_index()
    )
    grouped["avg_match_length_min"] = (
        (grouped["avg_match_length_sec"].astype(float) / 60.0).round(1)
    )

    grouped = grouped.sort_values("games", ascending=False, kind="stable")
    return grouped[MAP_SUMMARY_COLUMNS].reset_index(drop=True)
