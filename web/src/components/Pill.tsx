type Variant = "win" | "loss" | "draw" | "neutral";

type Props = {
  variant: Variant;
  children: React.ReactNode;
  className?: string;
};

const VARIANT_CLASSES: Record<Variant, string> = {
  win: "bg-win-soft text-win",
  loss: "bg-loss-soft text-loss",
  draw: "bg-white/5 text-muted-strong",
  neutral: "bg-white/5 text-muted-strong",
};

export function Pill({ variant, children, className = "" }: Props) {
  return (
    <span
      className={`inline-flex h-5 min-w-[1.5rem] items-center justify-center rounded px-1.5 text-[11px] font-bold uppercase tracking-wider ${VARIANT_CLASSES[variant]} ${className}`}
    >
      {children}
    </span>
  );
}

export function resultPill(hasWon: boolean | null | undefined) {
  if (hasWon === true) return <Pill variant="win">W</Pill>;
  if (hasWon === false) return <Pill variant="loss">L</Pill>;
  return <Pill variant="neutral">—</Pill>;
}
