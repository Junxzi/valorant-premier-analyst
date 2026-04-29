/** External VOD link for match rows; shows an em dash when unset. */

export function VodCell({
  url,
  className = "",
}: {
  url: string | null | undefined;
  className?: string;
}) {
  if (!url) {
    return (
      <span className={`tabular-nums text-muted ${className}`.trim()}>—</span>
    );
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className={`text-xs font-semibold uppercase tracking-wider text-accent underline-offset-2 hover:underline ${className}`.trim()}
    >
      VOD
    </a>
  );
}
