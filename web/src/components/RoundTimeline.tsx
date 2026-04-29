import type { MatchTeamSummary, RoundEntry } from "@/lib/api";

type Props = {
  rounds: RoundEntry[];
  blue: MatchTeamSummary | null;
  red: MatchTeamSummary | null;
};

const HALF = 12;

export function RoundTimeline({ rounds, blue, red }: Props) {
  if (rounds.length === 0) {
    return (
      <div className="rounded-md border border-border bg-panel p-4">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-strong">
          Round Timeline
        </h2>
        <p className="mt-3 text-sm text-muted">
          このマッチのラウンドデータが取り込まれていません。
        </p>
      </div>
    );
  }

  const blueLabel = blue?.premier_team_tag ?? blue?.premier_team_name ?? "Blue";
  const redLabel = red?.premier_team_tag ?? red?.premier_team_name ?? "Red";

  return (
    <section className="rounded-md border border-border bg-panel p-4 overflow-x-auto">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-strong">
        Round Timeline
      </h2>

      <div className="inline-block min-w-full">
        {/* Round number header */}
        <div className="flex items-center mb-1">
          <div className="w-10 shrink-0" />
          {rounds.map((round, idx) => (
            <div
              key={round.round_num}
              className="flex items-center"
              style={{ marginLeft: idx === HALF ? 10 : 0 }}
            >
              <span className="w-7 mx-px text-center text-[10px] tabular-nums text-muted leading-none">
                {round.round_num}
              </span>
            </div>
          ))}
        </div>

        {/* Blue row */}
        <TeamRow
          label={blueLabel}
          rounds={rounds}
          side="blue"
        />

        {/* Red row */}
        <TeamRow
          label={redLabel}
          rounds={rounds}
          side="red"
        />
      </div>

      {/* Legend */}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted">
        <span className="inline-flex items-center gap-1">
          <span className="inline-flex h-4 w-4 items-center justify-center rounded-sm bg-rose-500/80 text-white"><FlameIcon /></span>
          ATK win
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-flex h-4 w-4 items-center justify-center rounded-sm bg-emerald-500/80 text-white"><ShieldIcon /></span>
          DEF win
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-flex h-4 w-4 rounded-sm border border-border bg-bg-elevated" />
          Loss
        </span>
        {[
          { icon: <ShieldIcon />, label: "Defused" },
          { icon: <FlameIcon />, label: "Detonated" },
          { icon: <GunIcon />, label: "Eliminated" },
          { icon: <ClockIcon />, label: "Time" },
        ].map(({ icon, label }) => (
          <span key={label} className="inline-flex items-center gap-1">
            <span className="inline-flex h-4 w-4 items-center justify-center rounded-sm bg-bg-elevated">
              {icon}
            </span>
            {label}
          </span>
        ))}
      </div>
    </section>
  );
}

function TeamRow({
  label,
  rounds,
  side,
}: {
  label: string;
  rounds: RoundEntry[];
  side: "blue" | "red";
}) {
  return (
    <div className="flex items-center mb-1">
      {/* Team label */}
      <div className="w-10 shrink-0 text-right pr-2">
        <span className="text-[11px] font-semibold text-muted-strong uppercase tracking-wide">
          {label}
        </span>
      </div>

      {/* Round cells */}
      {rounds.map((round, idx) => {
        const winner = (round.winning_team ?? "").toLowerCase();
        const won = winner === side;
        return (
          <div
            key={round.round_num}
            className="flex items-center"
            style={{ marginLeft: idx === HALF ? 10 : 0 }}
          >
            <RoundCell round={round} won={won} />
          </div>
        );
      })}
    </div>
  );
}

function RoundCell({
  round,
  won,
}: {
  round: RoundEntry;
  won: boolean;
}) {
  // Attacker wins by detonation (planted AND NOT defused)
  const atkWon =
    round.bomb_planted === true && round.bomb_defused !== true;

  const bg = won
    ? atkWon
      ? "bg-rose-500/80 border-rose-400/60 text-white"       // attacker win → red
      : "bg-emerald-500/80 border-emerald-400/60 text-white" // defender win → green
    : "bg-bg-elevated border-border";                         // loss → empty frame

  return (
    <div
      className={`w-7 h-7 mx-px flex items-center justify-center rounded-sm border text-[11px] ${bg}`}
      title={`R${round.round_num} · ${round.winning_team ?? "?"} · ${round.end_type ?? "?"}`}
    >
      {won && <EndTypeIcon round={round} />}
    </div>
  );
}

function EndTypeIcon({ round }: { round: RoundEntry }) {
  const t = (round.end_type ?? "").toLowerCase();
  if (t.includes("defus")) return <ShieldIcon />;
  if (t.includes("deton")) return <FlameIcon />;
  if (t.includes("elim")) return <GunIcon />;
  if (t.includes("time") || t.includes("expir") || t.includes("surren"))
    return <ClockIcon />;
  return <GunIcon />;
}

const CLS = "h-5 w-5";

function GunIcon() {
  return (
    <svg className={CLS} viewBox="0 0 20 20" fill="currentColor" aria-hidden>
      <path d="M3 7h8v2H9v1h2l1 3H4l1-3H3V7zM13 7l4 3-4 3V7z" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg className={CLS} viewBox="0 0 20 20" fill="currentColor" aria-hidden>
      <path d="M10 2L3 5v5c0 4.25 3.04 7.32 7 8 3.96-.68 7-3.75 7-8V5l-7-3zm-1.3 9.7L6.3 9.3l1.4-1.4L8.7 9l3.6-3.6 1.4 1.4-5 5z" />
    </svg>
  );
}

function FlameIcon() {
  return (
    <svg className={CLS} viewBox="0 0 20 20" fill="currentColor" aria-hidden>
      <path d="M10 2c0 0-6 5-6 9a6 6 0 0012 0c0-3-2-5-2-5s0 2-2 2c0 0 2-3-2-6zm0 11a2 2 0 110-4 2 2 0 010 4z" />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg
      className={CLS}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      aria-hidden
    >
      <circle cx="8" cy="8" r="6" />
      <path d="M8 4.5V8l2.4 1.5" />
    </svg>
  );
}
