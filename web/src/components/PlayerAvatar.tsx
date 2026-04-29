"use client";

type Props = {
  puuid: string;
  name?: string | null;
  size?: number;
};

/**
 * Player avatar: loads /players/{puuid}.png, falls back to a silhouette SVG.
 * Works as a client component so the onError handler can hide the broken image.
 */
export function PlayerAvatar({ puuid, name, size = 64 }: Props) {
  const src = `/players/${puuid}.png`;
  return (
    <div
      className="relative shrink-0 overflow-hidden rounded-[2px] border border-border-strong/60 bg-bg-elevated"
      style={{ width: size, height: size }}
      aria-hidden
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={name ?? ""}
        className="h-full w-full object-cover object-top"
        onError={(e) => {
          (e.currentTarget as HTMLImageElement).style.display = "none";
          const svg = e.currentTarget.parentElement?.querySelector("svg");
          if (svg) (svg as SVGElement).style.display = "block";
        }}
      />
      <svg
        viewBox="0 0 64 64"
        className="absolute inset-0 h-full w-full text-muted"
        aria-hidden
        fill="none"
        style={{ display: "none" }}
      >
        <ellipse cx={32} cy={24} rx={13} ry={13} stroke="currentColor" strokeWidth={2} opacity={0.35} />
        <path
          d="M16 53c4-13 28-13 32 0"
          stroke="currentColor"
          strokeWidth={2}
          opacity={0.35}
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}
