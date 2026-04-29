"use client";

import { useCallback, useState } from "react";

import { shortMatchId } from "@/lib/format";

type Props = {
  matchId: string;
  headLen?: number;
};

/**
 * Short ID with native tooltip for the full UUID — tooltips are usually not
 * selectable, so click copies the full ID to the clipboard.
 */
export function CopyMatchId({ matchId, headLen = 12 }: Props) {
  const [status, setStatus] = useState<"idle" | "copied" | "err">("idle");

  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(matchId);
      setStatus("copied");
      setTimeout(() => setStatus("idle"), 2000);
    } catch {
      setStatus("err");
      setTimeout(() => setStatus("idle"), 2500);
    }
  }, [matchId]);

  const title =
    status === "copied"
      ? "クリップボードにコピーしました"
      : status === "err"
        ? "コピーに失敗しました。URL バーまたは設定画面の match id を手でコピーしてください。"
        : `${matchId}\n（クリックで全文をコピー）`;

  return (
    <button
      type="button"
      onClick={copy}
      title={title}
      aria-label={`試合 ID ${matchId} をクリップボードにコピー`}
      className="mt-0.5 block max-w-full cursor-pointer text-right font-mono text-[11px] text-muted transition-colors hover:text-accent"
    >
      ID {shortMatchId(matchId, headLen)}
    </button>
  );
}
