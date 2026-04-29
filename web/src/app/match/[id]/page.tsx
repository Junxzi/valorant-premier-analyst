import Link from "next/link";
import { notFound } from "next/navigation";

import { RoundTimeline } from "@/components/RoundTimeline";
import { Scoreboard } from "@/components/Scoreboard";
import { ApiError, fetchMatch, fetchMatchEconomy } from "@/lib/api";
import type { MatchDetail, MatchTeamSummary, RoundEconomyEntry, RoundEntry } from "@/lib/api";
import {
  formatDuration,
  formatGameStart,
  teamDisplayName,
} from "@/lib/format";
import { mapSplashUrl } from "@/lib/maps";

type PageProps = {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string }>;
};

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "performance", label: "Performance" },
  { id: "economy", label: "Economy" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default async function MatchPage({ params, searchParams }: PageProps) {
  const { id: rawId } = await params;
  const { tab: rawTab } = await searchParams;
  const matchId = decodeURIComponent(rawId);
  const activeTab: TabId =
    TABS.some((t) => t.id === rawTab) ? (rawTab as TabId) : "overview";

  let data: MatchDetail;
  let economy: RoundEconomyEntry[] = [];
  try {
    data = await fetchMatch(matchId);
    if (activeTab === "economy") {
      economy = await fetchMatchEconomy(matchId).catch(() => []);
    }
  } catch (e) {
    if (e instanceof ApiError) {
      if (e.kind === "not_found") notFound();
      if (e.kind === "network") return <BackendDownState message={e.message} />;
    }
    throw e;
  }

  const blue = data.teams.find((t) => t.team.toLowerCase() === "blue") ?? null;
  const red = data.teams.find((t) => t.team.toLowerCase() === "red") ?? null;
  const bluePlayers = data.players.filter(
    (p) => (p.team ?? "").toLowerCase() === "blue",
  );
  const redPlayers = data.players.filter(
    (p) => (p.team ?? "").toLowerCase() === "red",
  );

  const baseUrl = `/match/${encodeURIComponent(matchId)}`;

  return (
    <div className="mx-auto max-w-6xl px-6 py-8 space-y-6">
      <MatchHero match={data} blue={blue} red={red} />

      {/* Tab navigation */}
      <nav className="border-b border-border">
        <ul className="-mb-px flex flex-wrap items-center gap-1">
          {TABS.map((tab) => {
            const active = tab.id === activeTab;
            return (
              <li key={tab.id}>
                <Link
                  href={tab.id === "overview" ? baseUrl : `${baseUrl}?tab=${tab.id}`}
                  className={`inline-flex h-9 items-center px-4 text-xs font-semibold uppercase tracking-wider transition-colors ${
                    active
                      ? "border-b-2 border-accent text-text-strong"
                      : "border-b-2 border-transparent text-muted hover:text-text"
                  }`}
                >
                  {tab.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Tab content */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          <RoundTimeline rounds={data.rounds} blue={blue} red={red} />
          <div className="space-y-6">
            {blue && <Scoreboard team={blue} players={bluePlayers} highlight />}
            {red && <Scoreboard team={red} players={redPlayers} highlight />}
          </div>
        </div>
      )}

      {activeTab === "performance" && (
        <div className="rounded-md border border-border bg-panel px-6 py-10 text-center">
          <p className="text-sm text-muted">N/A</p>
        </div>
      )}

      {activeTab === "economy" && (
        <div className="space-y-6">
          {economy.length > 0 ? (
            <EconomyChart economy={economy} blue={blue} red={red} rounds={data.rounds} />
          ) : (
            <div className="rounded-md border border-border bg-panel px-6 py-10 text-center">
              <p className="text-sm text-muted">経済データがありません。</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Match Hero
// ---------------------------------------------------------------------------

function MatchHero({
  match,
  blue,
  red,
}: {
  match: MatchDetail;
  blue: MatchTeamSummary | null;
  red: MatchTeamSummary | null;
}) {
  const splash = mapSplashUrl(match.map_name);
  const dateLabel = formatGameStart(match.game_start);
  const duration = formatDuration(match.game_length);
  const queueLabel =
    [match.queue, match.mode].filter(Boolean).join(" · ") || "Premier";

  return (
    <section className="relative overflow-hidden rounded-md border border-border bg-panel">
      {splash && (
        <div
          className="absolute inset-0 bg-cover bg-center opacity-25"
          style={{ backgroundImage: `url('${splash}')` }}
          aria-hidden
        />
      )}
      <div
        className="absolute inset-0 bg-gradient-to-b from-bg/40 via-bg/70 to-bg"
        aria-hidden
      />
      <div className="relative z-10 px-6 py-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-widest text-muted">
              {queueLabel}
            </p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight text-text-strong">
              {match.map_name ?? "Unknown Map"}
            </h1>
          </div>
          <div className="text-right text-xs text-muted">
            <p>{dateLabel}</p>
            <p className="mt-0.5">Duration {duration}</p>
            {match.vod_url ? (
              <p className="mt-1">
                <a
                  href={match.vod_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-semibold uppercase tracking-wider text-accent underline-offset-2 hover:underline"
                >
                  VOD
                </a>
              </p>
            ) : null}
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
          <TeamPlate team={blue} side="blue" align="left" />
          <ScoreCenter blue={blue} red={red} />
          <TeamPlate team={red} side="red" align="right" />
        </div>
      </div>
    </section>
  );
}

function ScoreCenter({
  blue,
  red,
}: {
  blue: MatchTeamSummary | null;
  red: MatchTeamSummary | null;
}) {
  const blueScore = blue?.rounds_won ?? null;
  const redScore = red?.rounds_won ?? null;

  return (
    <div className="flex items-center justify-center gap-3 font-mono text-5xl font-semibold tabular-nums">
      <span className={blue?.has_won ? "text-text-strong" : "text-muted"}>
        {blueScore ?? "—"}
      </span>
      <span className="text-2xl text-muted">:</span>
      <span className={red?.has_won ? "text-text-strong" : "text-muted"}>
        {redScore ?? "—"}
      </span>
    </div>
  );
}

function TeamPlate({
  team,
  side,
  align,
}: {
  team: MatchTeamSummary | null;
  side: "blue" | "red";
  align: "left" | "right";
}) {
  const sideName = side === "blue" ? "text-sky-300" : "text-rose-300";

  if (!team) {
    return (
      <div className={align === "right" ? "text-right" : ""}>
        <p className={`text-xs uppercase tracking-widest ${sideName}`}>
          {side === "blue" ? "Blue side" : "Red side"}
        </p>
        <p className="mt-1 text-lg font-semibold text-text-strong">—</p>
      </div>
    );
  }

  const teamName = (team.premier_team_name ?? "").trim();
  const teamTag = (team.premier_team_tag ?? "").trim();
  const hasPremier = teamName && teamTag;
  const teamHref = hasPremier
    ? `/team/${encodeURIComponent(teamName)}/${encodeURIComponent(teamTag)}`
    : null;
  const displayName = teamDisplayName(teamName, null, team.team);

  const result =
    team.has_won === true
      ? { label: "WIN", tone: "text-win" }
      : team.has_won === false
        ? { label: "LOSS", tone: "text-loss" }
        : { label: "—", tone: "text-muted" };

  return (
    <div className={align === "right" ? "text-right" : ""}>
      <p className={`text-xs uppercase tracking-widest ${sideName}`}>
        {side === "blue" ? "Blue side" : "Red side"}
      </p>
      <p className="mt-1 text-2xl font-semibold leading-tight text-text-strong">
        {teamHref ? (
          <Link href={teamHref} className="hover:underline">
            {displayName}
          </Link>
        ) : (
          displayName
        )}
      </p>
      {teamTag && <p className="text-sm text-muted">#{teamTag}</p>}
      <p
        className={`mt-1 text-[11px] font-bold uppercase tracking-wider ${result.tone}`}
      >
        {result.label}
      </p>
    </div>
  );
}

function BackendDownState({ message }: { message: string }) {
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <div className="rounded-md border border-loss/40 bg-loss-soft p-6">
        <h2 className="text-lg font-semibold text-loss">Backend unreachable</h2>
        <p className="mt-2 text-sm text-text">
          バックエンド API に接続できませんでした。FastAPI サーバが起動しているか確認してください。
        </p>
        <p className="mt-3 text-xs text-muted">{message}</p>
        <Link
          href="/"
          className="mt-4 inline-flex items-center gap-1 text-sm text-accent hover:text-accent-strong"
        >
          ← Home に戻る
        </Link>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Economy Chart
// ---------------------------------------------------------------------------

const ECO_TIERS = [
  { label: "Eco",      symbol: "",    max: 5_000 },
  { label: "Semi-eco", symbol: "$",   max: 10_000 },
  { label: "Semi-buy", symbol: "$$",  max: 20_000 },
  { label: "Full buy", symbol: "$$$", max: Infinity },
] as const;

function ecoTier(total: number) {
  return ECO_TIERS.find((t) => total < t.max) ?? ECO_TIERS[ECO_TIERS.length - 1];
}

function fmtK(n: number) {
  if (n < 1000) return `${n}`;
  return `${(n / 1000).toFixed(1)}k`;
}

function EconomyChart({
  economy,
  blue,
  red,
  rounds,
}: {
  economy: RoundEconomyEntry[];
  blue: MatchTeamSummary | null;
  red: MatchTeamSummary | null;
  rounds: RoundEntry[];
}) {
  const blueTag = blue?.premier_team_tag ?? blue?.premier_team_name ?? "Blue";
  const redTag = red?.premier_team_tag ?? red?.premier_team_name ?? "Red";

  const roundWinner = new Map<number, string>(
    rounds.map((r) => [r.round_num, (r.winning_team ?? "").toLowerCase()]),
  );

  const roundsMap = new Map<number, RoundEntry>(
    rounds.map((r) => [r.round_num, r]),
  );

  const byRound = new Map<number, Record<string, RoundEconomyEntry>>();
  for (const e of economy) {
    if (!byRound.has(e.round_num)) byRound.set(e.round_num, {});
    byRound.get(e.round_num)![e.team.toLowerCase()] = e;
  }

  const allRounds = Array.from(new Set(economy.map((e) => e.round_num))).sort(
    (a, b) => a - b,
  );

  const summaryFor = (side: "blue" | "red") => {
    const pistols = [1, 13].filter((r) => allRounds.includes(r));
    const pistolWon = pistols.filter((r) => roundWinner.get(r) === side).length;
    const counts = [0, 0, 0, 0];
    const wins = [0, 0, 0, 0];
    for (const rnd of allRounds) {
      if (rnd === 1 || rnd === 13) continue; // pistol rounds excluded
      const entry = byRound.get(rnd)?.[side];
      if (!entry) continue;
      const tidx = ECO_TIERS.findIndex((t) => entry.total_loadout < t.max);
      const i = tidx >= 0 ? tidx : ECO_TIERS.length - 1;
      counts[i]++;
      if (roundWinner.get(rnd) === side) wins[i]++;
    }
    return { pistolWon, counts, wins };
  };

  const blueStats = summaryFor("blue");
  const redStats = summaryFor("red");

  const half1 = allRounds.filter((r) => r <= 12);
  const half2 = allRounds.filter((r) => r > 12);
  const halves = [half1, half2].filter((h) => h.length > 0);

  const LABEL_W = "w-16 shrink-0";
  const CELL_W = "w-9";

  return (
    <section className="rounded-md border border-border bg-panel overflow-x-auto">
      {/* Summary table */}
      <div className="px-5 pt-4 pb-3">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-[11px] text-muted uppercase tracking-wide">
              <th className="text-left font-medium py-1.5 pr-4 w-28">Team</th>
              <th className="text-center font-medium py-1.5 px-3">Pistol Won</th>
              {ECO_TIERS.map((t, i) => (
                <th key={i} className="text-center font-medium py-1.5 px-3">
                  {t.symbol || "Eco"} (won)
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(["blue", "red"] as const).map((side) => {
              const label = side === "blue" ? blueTag : redTag;
              const stats = side === "blue" ? blueStats : redStats;
              return (
                <tr key={side} className="border-t border-border/50">
                  <td className="py-2 pr-4 font-semibold text-text-strong">{label}</td>
                  <td className="py-2 px-3 text-center tabular-nums font-medium text-text-strong">
                    {stats.pistolWon}
                  </td>
                  {stats.counts.map((count, i) => (
                    <td key={i} className="py-2 px-3 text-center tabular-nums text-muted-strong">
                      {count}{" "}
                      <span className="text-muted">({stats.wins[i]})</span>
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>

        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[11px] text-muted">
          <span className="text-yellow-500/80 font-bold">P</span><span>Pistol</span>
          <span className="text-muted/60 ml-2">team loadout:</span>
          <span>Eco: 0–5k</span>
          <span>$ Semi-eco: 5–10k</span>
          <span>$$ Semi-buy: 10–20k</span>
          <span>$$$ Full buy: 20k+</span>
        </div>
      </div>

      <div className="border-t border-border" />

      {/* Per-round grid by half */}
      <div className="px-5 py-4 space-y-8">
        {halves.map((half, hi) => (
          <div key={hi}>
            <p className="text-[10px] uppercase tracking-widest text-muted mb-2">
              {hi === 0 ? "First Half" : "Second Half"}
            </p>

            {/* Round numbers */}
            <div className="flex items-center mb-0.5">
              <div className={LABEL_W} />
              {half.map((rnd) => (
                <div
                  key={rnd}
                  className={`${CELL_W} text-center text-[10px] tabular-nums text-muted`}
                >
                  {rnd}
                </div>
              ))}
            </div>

            {/* Team eco-tier rows + BANK */}
            {(["blue", "red"] as const).map((side) => (
              <div key={side}>
                <EconTeamRow
                  label={side === "blue" ? blueTag : redTag}
                  rounds={half}
                  byRound={byRound}
                  roundWinner={roundWinner}
                  roundsMap={roundsMap}
                  side={side}
                  labelW={LABEL_W}
                  cellW={CELL_W}
                />
                <EconBankRow
                  rounds={half}
                  byRound={byRound}
                  side={side}
                  labelW={LABEL_W}
                  cellW={CELL_W}
                />
              </div>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

function EconBankRow({
  rounds,
  byRound,
  side,
  labelW,
  cellW,
}: {
  rounds: number[];
  byRound: Map<number, Record<string, RoundEconomyEntry>>;
  side: "blue" | "red";
  labelW: string;
  cellW: string;
}) {
  return (
    <div className="flex items-center mb-1">
      <div className={`${labelW} text-right pr-2 text-[10px] font-medium text-muted/60`}>
        BANK
      </div>
      {rounds.map((rnd) => {
        const e = byRound.get(rnd)?.[side];
        const remaining =
          e ? e.total_loadout - e.total_spent : null;
        return (
          <div
            key={rnd}
            className={`${cellW} text-center text-[10px] tabular-nums text-muted/70`}
          >
            {remaining !== null ? fmtK(Math.round(remaining)) : "—"}
          </div>
        );
      })}
    </div>
  );
}

function EconTeamRow({
  label,
  rounds,
  byRound,
  roundWinner,
  roundsMap,
  side,
  labelW,
  cellW,
}: {
  label: string;
  rounds: number[];
  byRound: Map<number, Record<string, RoundEconomyEntry>>;
  roundWinner: Map<number, string>;
  roundsMap: Map<number, RoundEntry>;
  side: "blue" | "red";
  labelW: string;
  cellW: string;
}) {
  return (
    <div className="flex items-center my-px">
      <div
        className={`${labelW} text-right pr-2 text-[11px] font-semibold uppercase tracking-wide text-muted-strong truncate`}
      >
        {label}
      </div>
      {rounds.map((rnd) => {
        const entry = byRound.get(rnd)?.[side];
        const winner = roundWinner.get(rnd);
        const won = winner === side;
        const roundData = roundsMap.get(rnd);
        const atkWon =
          roundData?.bomb_planted === true && roundData?.bomb_defused !== true;
        const isPistol = rnd === 1 || rnd === 13;
        const tier = (!isPistol && entry) ? ecoTier(entry.total_loadout) : null;
        const bg = isPistol
          ? won
            ? "bg-yellow-500/80 border-yellow-400/60 text-white"
            : "bg-yellow-900/40 border-yellow-700/40 text-muted"
          : won
            ? atkWon
              ? "bg-rose-500/80 border-rose-400/60 text-white"
              : "bg-emerald-500/80 border-emerald-400/60 text-white"
            : "bg-bg-elevated border-border text-muted";
        return (
          <div key={rnd} className={`${cellW} px-px`}>
            <div
              className={`h-7 flex items-center justify-center rounded-sm border text-[11px] font-bold ${bg}`}
              title={
                isPistol
                  ? `R${rnd} · Pistol · team ${Math.round(entry?.total_loadout ?? 0).toLocaleString()}`
                  : `R${rnd} · ${tier?.label ?? "?"} · team ${Math.round(entry?.total_loadout ?? 0).toLocaleString()} (avg ${Math.round(entry?.avg_loadout ?? 0).toLocaleString()})`
              }
            >
              {isPistol ? "P" : won ? (tier?.symbol ?? "") : ""}
            </div>
          </div>
        );
      })}
    </div>
  );
}
