"use client";

import Link from "next/link";

import type { ReactNode } from "react";

import type { RosterMember } from "@/lib/api";
import type { StaffEntry } from "@/lib/teamConfig";
import { playerDisplayName } from "@/lib/format";
import { getPlayerConfig } from "@/lib/playerConfig";
import { PlayerAvatar } from "@/components/PlayerAvatar";

/**
 * vlr.gg 風の「CURRENT ROSTER」レイアウト。
 * アバター写真と国旗は後から差し替えられるようプレースホルダのみ。
 */

type Props = {
  members: RosterMember[];
  staff?: StaffEntry[];
};

export function CurrentRoster({ members, staff = [] }: Props) {
  if (members.length === 0) {
    return (
      <section className="space-y-3">
        <h2 className="text-[11px] font-bold uppercase tracking-[0.14em] text-muted-strong">
          Current roster
        </h2>
        <div className="rounded-md border border-border bg-panel px-5 py-8 text-center">
          <p className="text-sm text-muted">
            ロスター情報がまだありません。試合データを ingest すると表示されます。
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="space-y-3">
      <h2 className="text-[11px] font-bold uppercase tracking-[0.14em] text-muted-strong">
        Current roster
      </h2>

      <div className="rounded-md border border-border bg-panel px-5 py-6 md:px-6">
        <p className="mb-5 text-[10px] font-semibold uppercase tracking-wider text-muted">
          Players
        </p>
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {members.map((m) => (
            <RosterPlayerTile key={m.puuid} member={m} />
          ))}
        </div>

        {staff.length > 0 && (
          <div className="mt-10 border-t border-border pt-8">
            <p className="mb-5 text-[10px] font-semibold uppercase tracking-wider text-muted">
              Staff
            </p>
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {staff.map((s) => (
                <StaffTile key={`${s.name}-${s.role}`} entry={s} />
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function RosterPlayerTile({ member }: { member: RosterMember }) {
  const href = `/player/${encodeURIComponent(member.puuid)}`;
  const nameLine = riotIdLine(member);
  const isAnonymized = !member.name?.trim() && !member.tag?.trim();
  const flags = getPlayerConfig(member.puuid).flags ?? [];

  return (
    <Link
      href={href}
      className="group flex gap-4 rounded-sm outline-offset-2 transition-opacity hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
      title={member.puuid}
    >
      <PlayerAvatar puuid={member.puuid} name={member.name} />

      <div className="min-w-0 flex-1">
        <PlayerFlags flags={flags} />

        <div
          className={`mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm font-semibold leading-snug md:text-[15px] ${
            isAnonymized
              ? "italic text-muted group-hover:text-muted-strong"
              : "text-text-strong group-hover:text-accent"
          }`}
        >
          {nameLine.primary}
          {nameLine.suffix ? (
            <span className="font-medium text-muted group-hover:text-muted-strong">
              {nameLine.suffix}
            </span>
          ) : null}
        </div>

        {isAnonymized ? (
          <p className="mt-1 text-xs leading-relaxed text-muted">
            Riot ID は未取得です。ログに載った他試合から同一 puuid で復元されることがあります。
          </p>
        ) : null}

      </div>
    </Link>
  );
}

/**
 * メイン一行: 「名前」を強調し、`#タグ` を少し離して付ける。
 * アノニマスのときはプレースホルダのまま一本文字列。
 */
function riotIdLine(member: RosterMember): {
  primary: ReactNode;
  suffix?: ReactNode;
} {
  const n = (member.name ?? "").trim();
  const t = (member.tag ?? "").trim();
  if (!n && !t) {
    return { primary: playerDisplayName(null, null, member.puuid) };
  }
  if (n) return { primary: n };
  return { primary: `#${t}` };
}

function StaffTile({ entry }: { entry: StaffEntry }) {
  return (
    <div className="flex gap-4">
      <div
        className="relative h-[64px] w-[64px] shrink-0 overflow-hidden rounded-[2px] border border-border-strong/60 bg-bg-elevated"
        aria-hidden
      >
        <svg viewBox="0 0 64 64" className="h-full w-full text-muted" fill="none">
          <ellipse cx={32} cy={24} rx={13} ry={13} stroke="currentColor" strokeWidth={2} opacity={0.25} />
          <path d="M16 53c4-13 28-13 32 0" stroke="currentColor" strokeWidth={2} opacity={0.25} strokeLinecap="round" />
        </svg>
      </div>
      <div className="min-w-0 flex-1">
        <PlayerFlags flags={entry.flags ?? []} />
        <p className="mt-2 text-sm font-semibold leading-snug text-text-strong">
          {entry.name}
        </p>
        <p className="mt-1 text-[11px] leading-snug text-muted-strong">
          {entry.role}
        </p>
      </div>
    </div>
  );
}

function PlayerFlags({ flags }: { flags: string[] }) {
  if (flags.length === 0) {
    return (
      <span
        className="inline-block h-[14px] w-[20px] shrink-0 rounded-[2px] border border-border bg-bg-elevated"
        aria-hidden
      />
    );
  }
  return (
    <span className="inline-flex items-center gap-1">
      {flags.slice(0, 3).map((code) => (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={code}
          src={`https://flagcdn.com/w20/${code.toLowerCase()}.png`}
          srcSet={`https://flagcdn.com/w40/${code.toLowerCase()}.png 2x`}
          width={20}
          height={14}
          alt={code.toUpperCase()}
          className="rounded-[2px] object-cover"
        />
      ))}
    </span>
  );
}
