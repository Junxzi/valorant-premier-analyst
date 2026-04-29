"use client";

import { useRef, useState } from "react";

import { PlayerAvatar } from "@/components/PlayerAvatar";

type Props = {
  puuid: string;
  name?: string | null;
  size?: number;
};

export function AvatarUpload({ puuid, name, size = 72 }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Bust the cache after upload by appending a timestamp query
  const [cacheBust, setCacheBust] = useState(() => Date.now());

  const handleFile = async (file: File) => {
    setError(null);
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`/api/avatar/${encodeURIComponent(puuid)}`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.error ?? "Upload failed");
      } else {
        setCacheBust(Date.now());
      }
    } catch {
      setError("Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="group relative shrink-0" style={{ width: size, height: size }}>
      {/* Avatar with cache-busting key forces re-render */}
      <div key={cacheBust}>
        <PlayerAvatar puuid={puuid} name={name} size={size} />
      </div>

      {/* Upload overlay — visible on hover */}
      <button
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        title="プロフィール画像を変更"
        className="absolute inset-0 flex flex-col items-center justify-center rounded-[2px] bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity disabled:cursor-wait"
      >
        {uploading ? (
          <svg viewBox="0 0 24 24" className="w-6 h-6 text-white animate-spin" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
          </svg>
        ) : (
          <>
            <svg viewBox="0 0 24 24" className="w-5 h-5 text-white mb-0.5" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <span className="text-[9px] text-white font-semibold uppercase tracking-wide leading-none">
              変更
            </span>
          </>
        )}
      </button>

      {/* Hidden file input */}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
          e.target.value = "";
        }}
      />

      {/* Error toast */}
      {error && (
        <div
          className="absolute top-full left-0 mt-1 z-50 whitespace-nowrap rounded bg-loss px-2 py-1 text-[10px] text-white shadow"
          onClick={() => setError(null)}
        >
          {error}
        </div>
      )}
    </div>
  );
}
