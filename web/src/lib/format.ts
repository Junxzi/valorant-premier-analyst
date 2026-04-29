/**
 * Small presentation helpers shared by the dashboard pages.
 */

/**
 * Format a HenrikDev `game_start` value as a human-readable date.
 *
 * The API returns Unix epoch — historically HenrikDev has used both seconds
 * and milliseconds depending on the endpoint, so we sniff the magnitude.
 */
export function formatGameStart(value: number | null | undefined): string {
  if (value == null) return "—";
  const ms = value < 1e12 ? value * 1000 : value;
  const d = new Date(ms);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatScore(
  rw: number | null | undefined,
  rl: number | null | undefined,
): string {
  if (rw == null && rl == null) return "—";
  return `${rw ?? "-"}-${rl ?? "-"}`;
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}%`;
}

export function formatNumber(
  value: number | null | undefined,
  digits = 2,
): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function shortMatchId(id: string, head = 8): string {
  if (!id) return "";
  return id.length <= head ? id : `${id.slice(0, head)}…`;
}

/**
 * Build a Riot-ID style display label for a player.
 *
 * HenrikDev sometimes returns an empty string (not null) for `name` / `tag`
 * on very recent matches — Premier seasons appear to anonymize names during
 * the active period. We fall back to a stable handle derived from the puuid
 * so the scoreboard never has invisible / empty rows.
 */
export function playerDisplayName(
  name: string | null | undefined,
  tag: string | null | undefined,
  puuid?: string | null,
): string {
  const n = (name ?? "").trim();
  const t = (tag ?? "").trim();
  if (n && t) return `${n}#${t}`;
  if (n) return n;
  if (t) return `#${t}`;
  if (puuid) return `Player ${puuid.slice(0, 6)}`;
  return "Anonymous";
}

/**
 * Name-only variant — omits the `#tag` portion.
 * Use everywhere except the dedicated player detail page.
 */
export function playerName(
  name: string | null | undefined,
  puuid?: string | null,
): string {
  const n = (name ?? "").trim();
  if (n) return n;
  if (puuid) return `Player ${puuid.slice(0, 6)}`;
  return "Anonymous";
}

/**
 * Same shape as `playerDisplayName`, but used for opponent labels. Falls back
 * to `Team Red` / `Team Blue` when we know the side but not the name.
 */
export function teamDisplayName(
  name: string | null | undefined,
  tag: string | null | undefined,
  side?: string | null,
): string {
  const n = (name ?? "").trim();
  const t = (tag ?? "").trim();
  if (n && t) return `${n}#${t}`;
  if (n) return n;
  if (t) return `#${t}`;
  if (side) return `Team ${side}`;
  return "Unknown";
}

/**
 * Format a duration in seconds as `MM:SS` (or `H:MM:SS` if >= 1 hour).
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || seconds < 0 || Number.isNaN(seconds)) return "—";
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => n.toString().padStart(2, "0");
  if (h > 0) return `${h}:${pad(m)}:${pad(s)}`;
  return `${m}:${pad(s)}`;
}
