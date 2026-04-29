import Link from "next/link";

import { AgentBadge } from "@/components/AgentBadge";
import type { MatchPlayerStat, MatchTeamSummary } from "@/lib/api";
import { formatNumber, playerName, teamDisplayName } from "@/lib/format";

type Props = {
  team: MatchTeamSummary;
  players: MatchPlayerStat[];
  /** When true, the visual accents lean to the team's "highlight" color. */
  highlight?: boolean;
};

/**
 * vlr.gg-style scoreboard for a single team.
 *
 * Players are expected to already be sorted by ACS / score on the API side.
 * Renders a header row with the team identity + score, then a stat table.
 */
export function Scoreboard({ team, players, highlight = false }: Props) {
  const sideClasses = sideAccent(team.team);
  const winLabel =
    team.has_won === true ? "WIN" : team.has_won === false ? "LOSS" : "—";
  const winTone =
    team.has_won === true
      ? "text-win"
      : team.has_won === false
        ? "text-loss"
        : "text-muted";

  const teamLabel = teamDisplayName(
    team.premier_team_name,
    team.premier_team_tag,
    team.team,
  );

  return (
    <section
      className={`overflow-hidden rounded-md border ${
        highlight ? sideClasses.borderStrong : "border-border"
      } bg-panel`}
    >
      <header
        className={`flex items-center justify-between border-b border-border px-4 py-3 ${sideClasses.headerBg}`}
      >
        <div className="flex items-center gap-3">
          <span
            className={`inline-block h-2.5 w-2.5 rounded-full ${sideClasses.dot}`}
          />
          <div>
            <p className="text-xs uppercase tracking-wider text-muted">
              {team.team} side
            </p>
            <p className="text-sm font-semibold text-text-strong">
              {teamLabel}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs font-bold uppercase ${winTone}`}>
            {winLabel}
          </span>
          <span className="font-mono text-2xl font-semibold tabular-nums text-text-strong">
            {team.rounds_won ?? "—"}
          </span>
        </div>
      </header>

      {players.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted">
          このチームのプレイヤーデータがありません。
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-[11px] uppercase tracking-wider text-muted">
              <tr className="border-b border-border">
                <Th>Player</Th>
                <Th className="w-32">Agent</Th>
                <Th className="w-16 text-right">ACS</Th>
                <Th className="w-12 text-right">K</Th>
                <Th className="w-12 text-right">D</Th>
                <Th className="w-12 text-right">A</Th>
                <Th className="w-14 text-right">+/−</Th>
                <Th className="w-16 text-right">ADR</Th>
                <Th className="w-14 text-right">K/D</Th>
              </tr>
            </thead>
            <tbody>
              {players.map((p) => (
                <PlayerRow key={p.puuid} player={p} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function PlayerRow({ player }: { player: MatchPlayerStat }) {
  const playerLabel = playerName(player.name, player.puuid);
  const isAnonymized = !player.name?.trim() && !player.tag?.trim();

  const pmTone =
    player.plus_minus == null
      ? "text-muted"
      : player.plus_minus > 0
        ? "text-win"
        : player.plus_minus < 0
          ? "text-loss"
          : "text-muted-strong";

  const kdTone =
    player.kd_ratio == null
      ? "text-muted"
      : player.kd_ratio >= 1
        ? "text-win"
        : "text-loss";

  return (
    <tr className="border-b border-border/60 transition-colors hover:bg-panel-hover">
      <Td>
        <Link
          href={`/player/${encodeURIComponent(player.puuid)}`}
          className={`font-medium ${
            isAnonymized
              ? "italic text-muted hover:text-muted-strong"
              : "text-text hover:text-accent"
          }`}
          title={player.puuid}
        >
          {playerLabel}
        </Link>
      </Td>
      <Td>
        <AgentBadge agent={player.agent} size={26} />
      </Td>
      <Td className="text-right tabular-nums font-medium text-text-strong">
        {formatNumber(player.acs, 0)}
      </Td>
      <Td className="text-right tabular-nums text-text">{player.kills ?? "—"}</Td>
      <Td className="text-right tabular-nums text-text">{player.deaths ?? "—"}</Td>
      <Td className="text-right tabular-nums text-text">{player.assists ?? "—"}</Td>
      <Td className={`text-right tabular-nums ${pmTone}`}>
        {player.plus_minus == null
          ? "—"
          : `${player.plus_minus > 0 ? "+" : ""}${player.plus_minus}`}
      </Td>
      <Td className="text-right tabular-nums text-muted-strong">
        {formatNumber(player.adr, 0)}
      </Td>
      <Td className={`text-right tabular-nums font-medium ${kdTone}`}>
        {formatNumber(player.kd_ratio, 2)}
      </Td>
    </tr>
  );
}

function Th({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <th className={`px-3 py-2 text-left font-semibold ${className}`}>{children}</th>;
}

function Td({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <td className={`px-3 py-2.5 align-middle ${className}`}>{children}</td>;
}

function sideAccent(side: string): {
  borderStrong: string;
  headerBg: string;
  dot: string;
} {
  if (side.toLowerCase() === "blue") {
    return {
      borderStrong: "border-sky-500/50",
      headerBg: "bg-sky-500/10",
      dot: "bg-sky-400",
    };
  }
  if (side.toLowerCase() === "red") {
    return {
      borderStrong: "border-rose-500/50",
      headerBg: "bg-rose-500/10",
      dot: "bg-rose-400",
    };
  }
  return { borderStrong: "border-border", headerBg: "", dot: "bg-muted" };
}
