"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AgentBadge } from "@/components/AgentBadge";
import { resultPill } from "@/components/Pill";
import { fetchTeamMapStats } from "@/lib/api";
import type { TeamMapStat, TeamMapMatchDetail } from "@/lib/api";
import { formatGameStart, formatPercent, formatScore, teamDisplayName } from "@/lib/format";
import { mapThumbnailUrl, COMPETITIVE_MAPS } from "@/lib/maps";

export default function TeamStatsPage() {
  const params = useParams<{ name: string; tag: string }>();
  const name = decodeURIComponent(params.name);
  const tag = decodeURIComponent(params.tag);

  const [maps, setMaps] = useState<TeamMapStat[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTeamMapStats(name, tag)
      .then((d) => {
        const byName = new Map(d.maps.map((m) => [m.map_name?.toLowerCase(), m]));
        // Show all competitive maps; fill with zero-data for unplayed ones
        const merged: TeamMapStat[] = COMPETITIVE_MAPS.map((mapName) => {
          return byName.get(mapName.toLowerCase()) ?? emptyMapStat(mapName);
        });
        setMaps(merged);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [name, tag]);

  if (error) {
    return <p className="px-4 py-6 text-sm text-loss">{error}</p>;
  }
  if (!maps) {
    return <p className="px-4 py-6 text-sm text-muted">Loading…</p>;
  }
  if (maps.length === 0) {
    return <p className="px-4 py-6 text-sm text-muted">マップデータがありません。</p>;
  }

  return (
    <div className="rounded-md border border-border bg-panel overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="text-[10px] font-bold uppercase tracking-wider text-muted">
          <tr className="border-b border-border">
            <Th rowSpan={2} className="w-36 text-left">Map (#)</Th>
            <Th rowSpan={2} className="w-28">Expand</Th>
            <Th rowSpan={2} className="w-16 text-center">Win%</Th>
            <Th rowSpan={2} className="w-10 text-center text-win">W</Th>
            <Th rowSpan={2} className="w-10 text-center text-loss">L</Th>
            <Th colSpan={2} className="border-l border-border/60 text-center">1st Half</Th>
            <Th colSpan={3} className="border-l border-border/60 text-center bg-rose-500/10 text-rose-400">ATK</Th>
            <Th colSpan={3} className="border-l border-border/60 text-center bg-sky-500/10 text-sky-400">DEF</Th>
            <Th rowSpan={2} className="border-l border-border/60 text-left pl-4">Agent Compositions</Th>
          </tr>
          <tr className="border-b border-border">
            <Th className="border-l border-border/60 text-center">ATK 1st</Th>
            <Th className="text-center">DEF 1st</Th>
            <Th className="border-l border-border/60 text-center bg-rose-500/5">RW%</Th>
            <Th className="text-center bg-rose-500/5 text-win">RW</Th>
            <Th className="text-center bg-rose-500/5 text-loss">RL</Th>
            <Th className="border-l border-border/60 text-center bg-sky-500/5">RW%</Th>
            <Th className="text-center bg-sky-500/5 text-win">RW</Th>
            <Th className="text-center bg-sky-500/5 text-loss">RL</Th>
          </tr>
        </thead>
        <tbody>
          {maps.map((m) => (
            <MapRowGroup key={m.map_name ?? "unknown"} row={m} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MapRowGroup({ row }: { row: TeamMapStat }) {
  const [expanded, setExpanded] = useState(false);
  const thumb = mapThumbnailUrl(row.map_name);
  const unplayed = row.games === 0;
  const winTone = row.winrate_pct >= 50 ? "text-win" : row.games > 0 ? "text-loss" : "text-muted";

  return (
    <>
      {/* ── summary row ── */}
      <tr className={`border-b border-border/60 hover:bg-panel-hover ${unplayed ? "opacity-40" : ""}`}>
        <Td className="font-medium text-text-strong">
          {row.map_name ?? "Unknown"}
          <span className="ml-1.5 text-[11px] text-muted">({row.games})</span>
        </Td>

        {/* EXPAND cell: thumbnail + chevron */}
        <Td className="p-0">
          <button
            onClick={() => !unplayed && setExpanded((p) => !p)}
            className={`flex w-full items-center gap-2 px-3 py-2 transition-colors ${unplayed ? "cursor-default" : "hover:bg-panel-hover/60"}`}
            aria-label={expanded ? "Collapse" : "Expand"}
            disabled={unplayed}
          >
            {thumb ? (
              <div className="relative h-8 w-14 shrink-0 overflow-hidden rounded-[2px] border border-border/60">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={thumb}
                  alt={row.map_name ?? ""}
                  className="h-full w-full object-cover object-center"
                />
              </div>
            ) : (
              <div className="h-8 w-14 shrink-0 rounded-[2px] border border-border/60 bg-bg-elevated" />
            )}
            <span className="text-[11px] text-muted transition-transform duration-150" style={{ transform: expanded ? "rotate(180deg)" : "rotate(0deg)" }}>
              ▼
            </span>
          </button>
        </Td>

        <Td className={`text-center tabular-nums font-semibold ${winTone}`}>
          {formatPercent(row.winrate_pct, 0)}
        </Td>
        <Td className="text-center tabular-nums text-win">{row.wins}</Td>
        <Td className="text-center tabular-nums text-loss">{row.losses}</Td>

        <Td className="border-l border-border/60 text-center tabular-nums">
          <SideFirstCell wins={row.atk_first_wins} games={row.atk_first_games} />
        </Td>
        <Td className="text-center tabular-nums">
          <SideFirstCell wins={row.def_first_wins} games={row.def_first_games} />
        </Td>

        <Td className="border-l border-border/60 text-center tabular-nums bg-rose-500/5">
          <RwPct value={row.atk_rw_pct} />
        </Td>
        <Td className="text-center tabular-nums bg-rose-500/5 text-win">{row.atk_rounds_won}</Td>
        <Td className="text-center tabular-nums bg-rose-500/5 text-loss">{row.atk_rounds_lost}</Td>

        <Td className="border-l border-border/60 text-center tabular-nums bg-sky-500/5">
          <RwPct value={row.def_rw_pct} />
        </Td>
        <Td className="text-center tabular-nums bg-sky-500/5 text-win">{row.def_rounds_won}</Td>
        <Td className="text-center tabular-nums bg-sky-500/5 text-loss">{row.def_rounds_lost}</Td>

        <Td className="border-l border-border/60 pl-4">
          <div className="flex flex-col gap-2">
            {row.agent_comps.slice(0, 2).map((comp, i) => (
              <div key={i} className="flex items-center gap-1 flex-wrap">
                {comp.agents.map((agent) => (
                  <AgentBadge key={agent} agent={agent} size={22} showName={false} />
                ))}
                {comp.count > 1 && (
                  <span className="ml-1 text-[10px] text-muted tabular-nums">×{comp.count}</span>
                )}
              </div>
            ))}
          </div>
        </Td>
      </tr>

      {/* ── per-match detail rows ── */}
      {expanded && row.matches.map((m) => (
        <MatchDetailRow key={m.match_id} match={m} />
      ))}
    </>
  );
}

function MatchDetailRow({ match }: { match: TeamMapMatchDetail }) {
  const href = `/match/${encodeURIComponent(match.match_id)}`;
  const oppLabel = teamDisplayName(match.opponent_name, match.opponent_tag, null);

  const atkBadge = (
    <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold bg-rose-500/20 text-rose-300">
      ATK
    </span>
  );
  const defBadge = (
    <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold bg-sky-500/20 text-sky-300">
      DEF
    </span>
  );

  const firstHalfAtk = match.atk_first ? atkBadge : defBadge;
  const firstHalfScore = match.atk_first
    ? `${match.atk_rounds_won}/${match.atk_rounds_lost}`
    : `${match.def_rounds_won}/${match.def_rounds_lost}`;
  const secondHalfAtk = match.atk_first ? defBadge : atkBadge;
  const secondHalfScore = match.atk_first
    ? `${match.def_rounds_won}/${match.def_rounds_lost}`
    : `${match.atk_rounds_won}/${match.atk_rounds_lost}`;

  return (
    <tr className="border-b border-border/40 bg-bg-elevated/40 text-xs hover:bg-panel-hover/60">
      {/* Date */}
      <Td className="pl-6 text-muted tabular-nums">
        {formatGameStart(match.game_start)}
      </Td>

      {/* Expand cell: result pill + score + opponent */}
      <Td colSpan={4} className="whitespace-nowrap">
        <Link href={href} className="flex items-center gap-3 hover:text-accent">
          {resultPill(match.has_won)}
          <span className="font-mono font-semibold tabular-nums text-text-strong">
            {formatScore(match.rounds_won, match.rounds_lost)}
          </span>
          <span className="text-text">{oppLabel}</span>
        </Link>
      </Td>

      {/* 1st half side + score */}
      <Td colSpan={2} className="border-l border-border/60">
        <div className="flex items-center gap-1">
          {firstHalfAtk}
          <span className="tabular-nums text-muted-strong">{firstHalfScore}</span>
        </div>
      </Td>

      {/* ATK rounds (2nd half if def-first) */}
      <Td colSpan={3} className="border-l border-border/60 bg-rose-500/5">
        <div className="flex items-center gap-1">
          {secondHalfAtk}
          <span className="tabular-nums text-muted-strong">{secondHalfScore}</span>
        </div>
      </Td>

      {/* DEF placeholder — keep column alignment */}
      <Td colSpan={3} className="border-l border-border/60 bg-sky-500/5" />

      {/* Agent icons */}
      <Td className="border-l border-border/60 pl-4">
        <div className="flex items-center gap-1 flex-wrap">
          {match.agents.map((agent) => (
            <AgentBadge key={agent} agent={agent} size={20} showName={false} />
          ))}
        </div>
      </Td>
    </tr>
  );
}

function emptyMapStat(mapName: string): TeamMapStat {
  return {
    map_name: mapName,
    games: 0, wins: 0, losses: 0, winrate_pct: 0,
    atk_rounds_won: 0, atk_rounds_lost: 0, atk_rw_pct: 0,
    def_rounds_won: 0, def_rounds_lost: 0, def_rw_pct: 0,
    atk_first_games: 0, atk_first_wins: 0, atk_first_winrate_pct: 0,
    def_first_games: 0, def_first_wins: 0, def_first_winrate_pct: 0,
    agent_comps: [], matches: [],
  };
}

function SideFirstCell({ wins, games }: { wins: number; games: number }) {
  if (games === 0) return <span className="text-muted">—</span>;
  const pct = Math.round((wins / games) * 100);
  const tone = pct >= 50 ? "text-win" : "text-loss";
  return (
    <span className={`font-medium ${tone}`}>
      {wins}W/{games - wins}L
      <span className="ml-1 text-[10px] text-muted">({pct}%)</span>
    </span>
  );
}

function RwPct({ value }: { value: number }) {
  const tone = value >= 50 ? "text-win" : "text-loss";
  return <span className={`font-semibold ${tone}`}>{formatPercent(value, 0)}</span>;
}

function Th({
  children,
  className = "",
  colSpan,
  rowSpan,
}: {
  children?: React.ReactNode;
  className?: string;
  colSpan?: number;
  rowSpan?: number;
}) {
  return (
    <th className={`px-3 py-2 font-bold ${className}`} colSpan={colSpan} rowSpan={rowSpan}>
      {children}
    </th>
  );
}

function Td({
  children,
  className = "",
  colSpan,
}: {
  children?: React.ReactNode;
  className?: string;
  colSpan?: number;
}) {
  return (
    <td className={`px-3 py-2.5 align-middle ${className}`} colSpan={colSpan}>
      {children}
    </td>
  );
}
