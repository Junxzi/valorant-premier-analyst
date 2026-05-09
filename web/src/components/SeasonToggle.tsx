"use client";

import type { SeasonId } from "@/lib/seasons";

/**
 * Season filter pill — same look as the strategy page toggle, extracted so
 * the Matches and Playoffs tabs can reuse it. ``"all"`` means "no filter".
 */
export type SeasonFilter = "all" | SeasonId;

export type SeasonOption = {
  value: SeasonFilter;
  label: string;
};

export const DEFAULT_SEASON_OPTIONS: SeasonOption[] = [
  { value: "all", label: "全体" },
  { value: "v26a3", label: "V26A3" },
];

type Props = {
  value: SeasonFilter;
  onChange: (next: SeasonFilter) => void;
  options?: SeasonOption[];
  className?: string;
};

export function SeasonToggle({
  value,
  onChange,
  options = DEFAULT_SEASON_OPTIONS,
  className = "",
}: Props) {
  return (
    <div
      className={`flex rounded-md border border-border overflow-hidden text-[11px] font-semibold uppercase tracking-wider ${className}`}
    >
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`px-3 py-1 transition-colors ${
            value === opt.value
              ? "bg-accent text-bg-elevated"
              : "text-muted hover:text-text hover:bg-bg-elevated"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
