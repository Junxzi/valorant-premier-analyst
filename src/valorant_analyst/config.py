"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Legacy "data/" tree — kept around as a *seed* for fresh deployments and as
# the source for one-shot migration into PERSIST_ROOT. New writes never go
# here; see PERSIST_ROOT below.
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"

# Single persistence root — everything that must survive a redeploy lives
# here. On Railway this is mounted as a Volume at /app/db so a single mount
# keeps the DuckDB database, raw match archive, strategy/notes/bios JSON,
# vods, and roster history all persistent.
DB_DIR = PROJECT_ROOT / "db"
PERSIST_ROOT = DB_DIR

DEFAULT_DB_PATH = PERSIST_ROOT / "valorant.duckdb"
DEFAULT_RAW_MATCHES_PATH = RAW_DIR / "latest_matches.json"  # transient bundle, ok in data/
DEFAULT_REPORT_PATH = REPORTS_DIR / "latest_report.md"
DEFAULT_ARCHIVE_DIR = PERSIST_ROOT / "raw" / "matches"
DEFAULT_ROSTER_HISTORY_PATH = PERSIST_ROOT / "roster_history.json"
DEFAULT_STRATEGY_DIR = PERSIST_ROOT / "strategy"
DEFAULT_NOTES_DIR = PERSIST_ROOT / "notes"
DEFAULT_BIOS_DIR = PERSIST_ROOT / "bios"
DEFAULT_VODS_PATH = PERSIST_ROOT / "vods.json"

# Legacy paths — only read for the one-shot migration on server startup.
LEGACY_ARCHIVE_DIR = RAW_DIR / "matches"
LEGACY_ROSTER_HISTORY_PATH = DATA_DIR / "roster_history.json"
LEGACY_STRATEGY_DIR = DATA_DIR / "strategy"
LEGACY_NOTES_DIR = DATA_DIR / "notes"
LEGACY_BIOS_DIR = DATA_DIR / "bios"
LEGACY_VODS_PATH = DATA_DIR / "vods.json"


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class AppConfig:
    """Strongly typed view of environment-driven configuration."""

    henrik_api_key: str
    region: str
    name: str
    tag: str
    match_size: int
    roster_entries: tuple[str, ...]
    roster_min_present: int
    premier_team_name: str
    premier_team_tag: str

    def require_api_key(self) -> str:
        """Return the API key, raising a friendly error if it is missing."""
        if not self.henrik_api_key:
            raise ConfigError(
                "HENRIK_API_KEY is not set. "
                "Copy .env.example to .env and add your HenrikDev API key."
            )
        return self.henrik_api_key

    def require_player(self) -> tuple[str, str]:
        """Return the (name, tag) tuple, raising if either is missing."""
        if not self.name or not self.tag:
            raise ConfigError(
                "VALORANT_NAME and VALORANT_TAG must be set in .env "
                "(e.g. VALORANT_NAME=YourRiotID, VALORANT_TAG=1234)."
            )
        return self.name, self.tag

    def require_premier_team(self) -> tuple[str, str]:
        """Return (team_name, team_tag), raising if either is missing."""
        if not self.premier_team_name or not self.premier_team_tag:
            raise ConfigError(
                "PREMIER_TEAM_NAME and PREMIER_TEAM_TAG must be set in .env "
                "(your Premier team's display name and 3-character tag, "
                "not your personal Riot ID)."
            )
        return self.premier_team_name, self.premier_team_tag

    def require_roster(self) -> tuple[str, ...]:
        """Return the configured roster, raising if it is empty."""
        if not self.roster_entries:
            raise ConfigError(
                "PREMIER_ROSTER is empty. Add a comma-separated list to .env, "
                "e.g. PREMIER_ROSTER=Name1#JP1,Name2#JP1,Name3#JP1. "
                "Run `roster-discover` first to find your teammates' Riot IDs."
            )
        return self.roster_entries


def _parse_int(value: str | None, default: int, field: str) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{field} must be an integer, got: {value!r}") from exc


def _parse_roster(value: str | None) -> tuple[str, ...]:
    """Parse a comma-separated roster value from .env into a clean tuple.

    Each entry can be a Riot ID (``Name#Tag``) or a raw PUUID. Whitespace is
    trimmed and empty entries are dropped.
    """
    if not value:
        return ()
    parts = [p.strip() for p in value.split(",")]
    return tuple(p for p in parts if p)


def load_config() -> AppConfig:
    """Load configuration from a .env file (if present) and the environment."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)

    return AppConfig(
        henrik_api_key=os.getenv("HENRIK_API_KEY", "").strip(),
        region=os.getenv("VALORANT_REGION", "ap").strip() or "ap",
        name=os.getenv("VALORANT_NAME", "").strip(),
        tag=os.getenv("VALORANT_TAG", "").strip(),
        match_size=_parse_int(os.getenv("MATCH_SIZE"), default=10, field="MATCH_SIZE"),
        roster_entries=_parse_roster(os.getenv("PREMIER_ROSTER")),
        roster_min_present=_parse_int(
            os.getenv("ROSTER_MIN_PRESENT"),
            default=4,
            field="ROSTER_MIN_PRESENT",
        ),
        premier_team_name=os.getenv("PREMIER_TEAM_NAME", "").strip(),
        premier_team_tag=os.getenv("PREMIER_TEAM_TAG", "").strip(),
    )
