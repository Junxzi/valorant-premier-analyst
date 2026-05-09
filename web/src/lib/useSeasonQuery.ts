"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

import type { SeasonFilter } from "@/components/SeasonToggle";

import { DEFAULT_SEASON, isValidSeason } from "./seasonQuery";

/**
 * Read/write the season filter from `?season=` in the URL.
 *
 * - The URL is the source of truth so the toggle survives copy-paste,
 *   refresh, and tab navigation inside the same page chrome.
 * - Defaults to V26A3 when the param is absent or invalid (matches the
 *   project's current-season-first design).
 * - Uses `router.replace` (not `push`) so the back button doesn't fill up
 *   with toggle-flip entries.
 *
 * NOTE: server components must import the corresponding helpers from
 * `seasonQuery.ts` instead — pulling this hook (or anything from this
 * `"use client"` module) into a server-side render path will throw.
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
    () => (isValidSeason(raw) ? (raw as SeasonFilter) : DEFAULT_SEASON),
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
