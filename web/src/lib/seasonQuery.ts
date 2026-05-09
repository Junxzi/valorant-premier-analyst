/**
 * Server-safe helpers for the `?season=` URL query.
 *
 * Lives in a non-`"use client"` module so server components (e.g. the
 * player page) can import these without dragging client-only hooks
 * (`useSearchParams`, `useRouter`) into the server bundle. The companion
 * `useSeasonQuery()` hook in `useSeasonQuery.ts` re-uses this same
 * validator so client and server agree on what counts as a valid value.
 */

import type { SeasonFilter } from "@/components/SeasonToggle";
import { findSeasonById, type SeasonId } from "@/lib/seasons";

/** Default season when the `?season=` param is missing or invalid. */
export const DEFAULT_SEASON: SeasonFilter = "v26a3";

const VALID_LITERALS: ReadonlySet<SeasonFilter> = new Set<SeasonFilter>(["all"]);

export function isValidSeason(v: string | null | undefined): v is SeasonFilter {
  if (v == null) return false;
  if (VALID_LITERALS.has(v as SeasonFilter)) return true;
  return findSeasonById(v as SeasonId) !== undefined;
}

/**
 * Read the season from a server-side `searchParams` object (Next.js App
 * Router page prop). Returns the default when the value is absent or
 * unrecognized.
 */
export function readSeasonFromSearchParams(
  raw: string | string[] | undefined,
): SeasonFilter {
  const v = Array.isArray(raw) ? raw[0] : raw;
  return isValidSeason(v) ? (v as SeasonFilter) : DEFAULT_SEASON;
}
