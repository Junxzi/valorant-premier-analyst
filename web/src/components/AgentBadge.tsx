import { agentIconUrl, roleClasses } from "@/lib/agents";

type Props = {
  agent: string | null | undefined;
  size?: number;
  showName?: boolean;
};

/**
 * Agent display: square icon badge with the agent name on the right.
 *
 * Uses `valorant-api.com`'s public CDN for the icon and falls back to a
 * monogram chip when we don't have the agent in our lookup (or the API
 * returns an unfamiliar string).
 */
export function AgentBadge({ agent, size = 28, showName = true }: Props) {
  const icon = agentIconUrl(agent);
  const monogram = (agent ?? "?").slice(0, 1).toUpperCase();

  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={`relative inline-flex items-center justify-center overflow-hidden rounded border ${roleClasses(agent)}`}
        style={{ width: size, height: size }}
      >
        {icon ? (
          // External CDN — keep as a plain <img> to avoid Next.js domain config.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={icon}
            alt={agent ?? "agent"}
            width={size}
            height={size}
            className="object-cover"
            loading="lazy"
          />
        ) : (
          <span className="text-[11px] font-bold tabular-nums">{monogram}</span>
        )}
      </span>
      {showName && (
        <span className="text-sm font-medium text-text">{agent ?? "—"}</span>
      )}
    </span>
  );
}
