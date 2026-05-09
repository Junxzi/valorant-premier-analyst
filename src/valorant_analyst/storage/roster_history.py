"""Persistent roster history for Premier teams.

The Premier team API only returns the *current* members. As soon as a player
leaves the team, they disappear from that response — but their past matches
stay in the archive forever, and we still want them to show up in roster
filters and analyses.

This module owns ``data/roster_history.json``: a small JSON file keyed by
``"{team_name}#{team_tag}"`` that accumulates every member ever seen on the
team. Each entry records when we first/last saw them and whether they're
currently on the active roster.

The merge step is the heart of it:

* Members in *current* that we already have → update ``last_seen_at`` and
  flip ``is_current`` back to ``True`` (covers re-joins).
* Members in *current* that are new → insert with ``first_seen_at = now``.
* Members already in history but missing from *current* → keep, but mark
  ``is_current = False``.

Identity is matched first by ``puuid`` (most stable), then by
``(name.lower(), tag.lower())`` as a fallback for entries that came from
a source that didn't have a puuid (e.g. ``PREMIER_ROSTER`` Riot IDs).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..analysis.roster import RosterEntry

ROSTER_HISTORY_FILENAME = "roster_history.json"


def _team_key(team_name: str, team_tag: str) -> str:
    return f"{team_name}#{team_tag}"


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class MemberRecord:
    """One member entry in the persisted roster history."""

    puuid: str | None
    name: str | None
    tag: str | None
    first_seen_at: str
    last_seen_at: str
    is_current: bool
    source: str  # "api" | "match_players" | "manual"

    def to_dict(self) -> dict[str, Any]:
        return {
            "puuid": self.puuid,
            "name": self.name,
            "tag": self.tag,
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "is_current": self.is_current,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemberRecord:
        return cls(
            puuid=_str_or_none(data.get("puuid")),
            name=_str_or_none(data.get("name")),
            tag=_str_or_none(data.get("tag")),
            first_seen_at=str(data.get("first_seen_at") or _utcnow_iso()),
            last_seen_at=str(data.get("last_seen_at") or _utcnow_iso()),
            is_current=bool(data.get("is_current", False)),
            source=str(data.get("source") or "manual"),
        )

    def to_roster_entry(self) -> RosterEntry:
        raw = (
            f"{self.name}#{self.tag}"
            if self.name and self.tag
            else (self.puuid or "")
        )
        return RosterEntry(
            raw=raw,
            name=self.name,
            tag=self.tag,
            puuid=self.puuid,
        )


@dataclass
class TeamHistory:
    """Per-team slice of the roster history."""

    last_synced_at: str | None
    members: list[MemberRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_synced_at": self.last_synced_at,
            "members": [m.to_dict() for m in self.members],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TeamHistory:
        members_raw = data.get("members") if isinstance(data, dict) else None
        members: list[MemberRecord] = []
        if isinstance(members_raw, list):
            for entry in members_raw:
                if isinstance(entry, dict):
                    members.append(MemberRecord.from_dict(entry))
        last = data.get("last_synced_at") if isinstance(data, dict) else None
        return cls(
            last_synced_at=str(last) if isinstance(last, str) else None,
            members=members,
        )


@dataclass
class RosterHistory:
    """Top-level container persisted to ``roster_history.json``."""

    teams: dict[str, TeamHistory] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"teams": {k: v.to_dict() for k, v in self.teams.items()}}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RosterHistory:
        if not isinstance(data, dict):
            return cls()
        teams_raw = data.get("teams")
        teams: dict[str, TeamHistory] = {}
        if isinstance(teams_raw, dict):
            for key, value in teams_raw.items():
                if isinstance(key, str) and isinstance(value, dict):
                    teams[key] = TeamHistory.from_dict(value)
        return cls(teams=teams)

    def team(self, team_name: str, team_tag: str) -> TeamHistory:
        """Return (creating if needed) the slice for *team_name#team_tag*."""
        key = _team_key(team_name, team_tag)
        slice_ = self.teams.get(key)
        if slice_ is None:
            slice_ = TeamHistory(last_synced_at=None, members=[])
            self.teams[key] = slice_
        return slice_


@dataclass
class MergeReport:
    """Summary of what changed during a single :func:`merge_team_members` call."""

    added: list[MemberRecord] = field(default_factory=list)
    rejoined: list[MemberRecord] = field(default_factory=list)
    departed: list[MemberRecord] = field(default_factory=list)
    updated: list[MemberRecord] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return (
            len(self.added) + len(self.rejoined) + len(self.departed) + len(self.updated)
        )


def _str_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def load_roster_history(path: Path) -> RosterHistory:
    """Load the roster history JSON, returning an empty container if missing."""
    path = Path(path)
    if not path.exists():
        return RosterHistory()
    try:
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return RosterHistory()
    if not isinstance(raw, dict):
        return RosterHistory()
    return RosterHistory.from_dict(raw)


def save_roster_history(history: RosterHistory, path: Path) -> None:
    """Persist *history* as pretty-printed UTF-8 JSON, creating parent dirs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(history.to_dict(), fh, ensure_ascii=False, indent=2, sort_keys=True)


def _entry_identity_keys(
    entry: RosterEntry | MemberRecord,
) -> tuple[str | None, tuple[str, str] | None]:
    """Return (puuid_key, riot_id_key) for matching against existing records."""
    puuid = entry.puuid
    name = entry.name
    tag = entry.tag
    riot = (
        (name.lower(), tag.lower())
        if isinstance(name, str) and isinstance(tag, str) and name and tag
        else None
    )
    return (puuid if isinstance(puuid, str) and puuid else None, riot)


def _find_existing(
    members: list[MemberRecord],
    puuid_key: str | None,
    riot_key: tuple[str, str] | None,
) -> MemberRecord | None:
    if puuid_key:
        for m in members:
            if m.puuid and m.puuid == puuid_key:
                return m
    if riot_key:
        for m in members:
            if (
                m.name
                and m.tag
                and (m.name.lower(), m.tag.lower()) == riot_key
            ):
                return m
    return None


def merge_team_members(
    history: RosterHistory,
    team_name: str,
    team_tag: str,
    current: list[RosterEntry],
    *,
    source: str,
    mark_missing_inactive: bool = True,
    default_is_current: bool = True,
    now_iso: str | None = None,
) -> MergeReport:
    """Merge *current* into *history* for ``team_name#team_tag``.

    Args:
        history: in-memory history object (mutated in place).
        team_name / team_tag: team identifier.
        current: roster entries observed *right now* (from API or DB scan).
        source: where these entries came from. Stored on newly-inserted
            records so we can later tell API members apart from
            database-scan-only members.
        mark_missing_inactive: if True, members already in history but absent
            from *current* get ``is_current = False``. Set to False when
            merging from a source that may be incomplete (e.g. database scan
            on a fresh DB).
        default_is_current: ``is_current`` value assigned to newly-inserted
            records. Authoritative sources (the team API) should leave this
            ``True``. The DuckDB scan should pass ``False``: it just tells us
            the player appeared on the team's side at some point, not that
            they're still on the active roster — only the API can confirm
            that, and an API call that *did* see them will flip the flag
            back to ``True`` on the next sync.
        now_iso: override the timestamp (used by tests). Defaults to now (UTC).

    Returns a :class:`MergeReport` describing what changed.
    """
    now = now_iso or _utcnow_iso()
    team = history.team(team_name, team_tag)
    report = MergeReport()

    seen_indices: set[int] = set()
    for entry in current:
        puuid_key, riot_key = _entry_identity_keys(entry)
        if puuid_key is None and riot_key is None:
            continue

        existing = _find_existing(team.members, puuid_key, riot_key)
        if existing is None:
            record = MemberRecord(
                puuid=entry.puuid,
                name=entry.name,
                tag=entry.tag,
                first_seen_at=now,
                last_seen_at=now,
                is_current=default_is_current,
                source=source,
            )
            team.members.append(record)
            seen_indices.add(len(team.members) - 1)
            report.added.append(record)
            continue

        was_current = existing.is_current
        existing.last_seen_at = now
        # Only authoritative sources (default_is_current=True) should be
        # able to flip an inactive member back to active. A DB scan saying
        # "I saw this puuid in old matches" is not enough to bring a
        # departed member back from is_current=False.
        if default_is_current:
            existing.is_current = True
        # Backfill missing identity fields if we now have them.
        if not existing.puuid and entry.puuid:
            existing.puuid = entry.puuid
        if not existing.name and entry.name:
            existing.name = entry.name
        if not existing.tag and entry.tag:
            existing.tag = entry.tag
        seen_indices.add(team.members.index(existing))

        if default_is_current and not was_current:
            report.rejoined.append(existing)
        else:
            report.updated.append(existing)

    if mark_missing_inactive:
        for idx, member in enumerate(team.members):
            if idx in seen_indices:
                continue
            if member.is_current:
                member.is_current = False
                report.departed.append(member)

    team.last_synced_at = now
    return report


def current_members(
    history: RosterHistory, team_name: str, team_tag: str
) -> list[RosterEntry]:
    """Return only members marked ``is_current = True`` for the given team."""
    team = history.teams.get(_team_key(team_name, team_tag))
    if team is None:
        return []
    return [m.to_roster_entry() for m in team.members if m.is_current]


def all_members(
    history: RosterHistory, team_name: str, team_tag: str
) -> list[RosterEntry]:
    """Return every member ever seen on the team (current + departed)."""
    team = history.teams.get(_team_key(team_name, team_tag))
    if team is None:
        return []
    return [m.to_roster_entry() for m in team.members]


def member_records(
    history: RosterHistory, team_name: str, team_tag: str
) -> list[MemberRecord]:
    """Return the raw :class:`MemberRecord` list (preserves is_current/timestamps)."""
    team = history.teams.get(_team_key(team_name, team_tag))
    if team is None:
        return []
    return list(team.members)
