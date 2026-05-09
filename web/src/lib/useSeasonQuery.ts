"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

import type { SeasonFilter } from "@/components/SeasonToggle";
import type { SeasonId } from "@/lib/seasons";
import { findSeasonById } from "@/lib/seasons";

/** Default season for newly-loaded pages — V26A3 is the active season. */
const DEFAULT_SEASON: SeasonFilter = "v26a3";

const VALID_VALUES: ReadonlySet<SeasonFilter> = new Set<SeasonFilter>(["all"]);
function isValid(v: string | null): v is SeasonFilter {
  if (v == null) return false;
  if (VALID_VALUES.has(v as SeasonFilter)) return true;
  return findSeasonById(v as SeasonId) !== undefined;
}

/**
 * Read/write the season filter from `?season=` in the URL.
 *
 * - The URL is the source of truth so the toggle survives copy-paste,
 *   refresh, and tab navigation inside the same page chrome.
 * - Defaults to V26A3 when the param is absent or invalid (matches the
 *   project's current-season-first design).
 * - Uses `router.replace` (not `push`) so the back button doesn't fill up
 *   with toggle-flip entries.
 */
export function useSeasonQuery(): {
  season: SeasonFilter;
  setSeason: (next: SeasonFilter) => void;
} {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const raw = searchParams.get("season");
  const season: SeasonFilter = useMemo(
    () => (isValid(raw) ? raw : DEFAULT_SEASON),
    [raw],
  );

  const setSeason = useCallback(
    (next: SeasonFilter) => {
      const params = new URLSearchParams(searchParams.toString());
      if (next === DEFAULT_SEASON) {
        params.delete("season");
      } else {
        params.set("season", next);
      }
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname, searchParams],
  );

  return { season, setSeason };
}

/**
 * Server-side variant — read the season from a `searchParams` object.
 * Used by Next.js page/layout server components that need to fetch
 * pre-filtered data from the API.
 */
export function readSeasonFromSearchParams(
  raw: string | string[] | undefined,
): SeasonFilter {
  const v = Array.isArray(raw) ? raw[0] : raw;
  return isValid(v ?? null) ? (v as SeasonFilter) : DEFAULT_SEASON;
}
