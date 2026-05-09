"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

export type TabSpec = {
  id: string;
  label: string;
  href: string;
};

type Props = {
  tabs: TabSpec[];
  /**
   * Query-string keys to carry forward when the user clicks a tab.
   * Defaults to `["season"]` so the V26A3 ↔ 全体 toggle stays sticky
   * across Overview / Stats / Matches / Strategy / Playoffs.
   */
  preserveQueryKeys?: readonly string[];
};

/**
 * vlr.gg-style underline-tab navigation.
 *
 * The active tab is auto-detected from `usePathname`: the tab whose `href`
 * is the longest prefix of the current path wins. This keeps individual
 * pages free of "am I active?" boilerplate.
 */
export function Tabs({ tabs, preserveQueryKeys = ["season"] }: Props) {
  const pathname = usePathname() ?? "";
  const searchParams = useSearchParams();

  const activeId = pickActive(tabs, pathname);

  // Build a query suffix carrying forward selected keys (e.g. ?season=v26a3)
  // so cross-tab navigation doesn't reset the active filter.
  const carry = new URLSearchParams();
  for (const key of preserveQueryKeys) {
    const v = searchParams.get(key);
    if (v != null) carry.set(key, v);
  }
  const carryStr = carry.toString();
  const querySuffix = carryStr ? `?${carryStr}` : "";

  return (
    <nav className="border-b border-border">
      <ul className="-mb-px flex flex-wrap items-center gap-1">
        {tabs.map((tab) => {
          const active = tab.id === activeId;
          return (
            <li key={tab.id}>
              <Link
                href={`${tab.href}${querySuffix}`}
                className={`inline-flex h-9 items-center px-4 text-xs font-semibold uppercase tracking-wider transition-colors ${
                  active
                    ? "border-b-2 border-accent text-text-strong"
                    : "border-b-2 border-transparent text-muted hover:text-text"
                }`}
                aria-current={active ? "page" : undefined}
              >
                {tab.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function pickActive(tabs: TabSpec[], pathname: string): string {
  // Longest matching prefix wins (so /team/a/b/matches beats /team/a/b).
  let best: TabSpec | null = null;
  for (const tab of tabs) {
    const href = stripTrailingSlash(tab.href);
    const path = stripTrailingSlash(pathname);
    if (path === href || path.startsWith(`${href}/`)) {
      if (!best || href.length > best.href.length) best = tab;
    }
  }
  return best?.id ?? tabs[0]?.id ?? "";
}

function stripTrailingSlash(s: string): string {
  return s.length > 1 && s.endsWith("/") ? s.slice(0, -1) : s;
}
