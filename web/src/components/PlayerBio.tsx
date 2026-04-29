"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { API_BASE_URL } from "@/lib/api";

type Props = {
  puuid: string;
  playerLabel: string;
};

type Mode = "view" | "confirm" | "edit";

export function PlayerBio({ puuid, playerLabel }: Props) {
  const [content, setContent] = useState<string | null>(null); // null = loading
  const [mode, setMode] = useState<Mode>("view");
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/players/${encodeURIComponent(puuid)}/bio`)
      .then((r) => r.json())
      .then((d) => { setContent(d.content ?? ""); setDraft(d.content ?? ""); })
      .catch(() => { setContent(""); setDraft(""); });
  }, [puuid]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [draft, mode]);

  const scheduleSave = (text: string) => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      setSaving(true);
      setSaved(false);
      fetch(`${API_BASE_URL}/api/players/${encodeURIComponent(puuid)}/bio`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text }),
      })
        .then(() => {
          setSaving(false);
          setSaved(true);
          setContent(text);
          setTimeout(() => setSaved(false), 2000);
        })
        .catch(() => setSaving(false));
    }, 1000);
  };

  const handleChange = (text: string) => {
    setDraft(text);
    scheduleSave(text);
  };

  const handleConfirm = () => {
    setMode("edit");
    setTimeout(() => textareaRef.current?.focus(), 50);
  };

  const handleDone = () => {
    setMode("view");
  };

  if (content === null) return null;

  // ── Confirmation dialog ──────────────────────────────────────────────────
  if (mode === "confirm") {
    return (
      <div className="mt-4 rounded-md border border-border bg-bg-elevated p-5">
        <p className="text-sm font-semibold text-text-strong">
          本人ですか？
        </p>
        <p className="mt-0.5 text-sm text-muted">
          Are you <span className="font-medium text-text">{playerLabel}</span>?
        </p>
        <p className="mt-2 text-xs text-muted/70">
          この BIO はあなた自身についての紹介文です。本人であることを確認してから編集してください。
          <br />
          This BIO is your personal introduction. Please confirm you are this player before editing.
        </p>
        <div className="mt-4 flex gap-3">
          <button
            onClick={handleConfirm}
            className="rounded-md bg-accent px-4 py-1.5 text-xs font-semibold text-bg-elevated hover:bg-accent-strong transition-colors"
          >
            はい、本人です / Yes, that&apos;s me
          </button>
          <button
            onClick={() => setMode("view")}
            className="rounded-md border border-border px-4 py-1.5 text-xs text-muted hover:text-text transition-colors"
          >
            キャンセル / Cancel
          </button>
        </div>
      </div>
    );
  }

  // ── Edit mode ────────────────────────────────────────────────────────────
  if (mode === "edit") {
    return (
      <div className="mt-4 rounded-md border border-border overflow-hidden">
        <div className="flex items-center gap-2 border-b border-border bg-bg-elevated px-3 py-1.5">
          <span className="text-[10px] uppercase tracking-widest text-muted">BIO — Edit</span>
          <div className="ml-auto flex items-center gap-3">
            {saving && <span className="text-[11px] text-muted">保存中…</span>}
            {saved && !saving && <span className="text-[11px] text-win">保存済み ✓</span>}
            <button
              onClick={handleDone}
              className="rounded-md bg-accent px-3 py-1 text-[11px] font-semibold text-bg-elevated hover:bg-accent-strong transition-colors"
            >
              完了 / Done
            </button>
          </div>
        </div>
        <textarea
          ref={textareaRef}
          value={draft}
          onChange={(e) => handleChange(e.target.value)}
          placeholder="自己紹介を書いてみましょう。Markdown 対応しています。&#10;Write your bio here. Markdown is supported."
          spellCheck={false}
          rows={4}
          className="w-full resize-none overflow-hidden bg-bg px-5 py-4 font-mono text-sm text-text leading-relaxed placeholder:text-muted/40 focus:outline-none"
        />
        <div className="border-t border-border bg-bg-elevated/40 px-3 py-1.5 text-[10px] text-muted/60">
          Markdown 対応 — # 見出し / **太字** / - リスト / &gt; 引用
        </div>
      </div>
    );
  }

  // ── View mode ────────────────────────────────────────────────────────────
  return (
    <div className="mt-4">
      {content.trim() ? (
        <div className="group relative">
          <div className="prose-note text-sm">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => <p className="text-sm text-text leading-relaxed mb-2 last:mb-0">{children}</p>,
                h1: ({ children }) => <h1 className="text-lg font-bold text-text-strong mb-2">{children}</h1>,
                h2: ({ children }) => <h2 className="text-base font-semibold text-text-strong mb-1">{children}</h2>,
                ul: ({ children }) => <ul className="list-disc list-inside text-sm text-text space-y-0.5 mb-2 pl-2">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal list-inside text-sm text-text space-y-0.5 mb-2 pl-2">{children}</ol>,
                li: ({ children }) => <li className="text-sm text-text">{children}</li>,
                strong: ({ children }) => <strong className="font-semibold text-text-strong">{children}</strong>,
                em: ({ children }) => <em className="italic text-muted-strong">{children}</em>,
                a: ({ href, children }) => <a href={href} className="text-accent hover:underline" target="_blank" rel="noopener noreferrer">{children}</a>,
                blockquote: ({ children }) => <blockquote className="border-l-4 border-accent pl-3 my-2 text-sm text-muted italic">{children}</blockquote>,
                hr: () => <hr className="my-3 border-border" />,
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
          <button
            onClick={() => setMode("confirm")}
            className="mt-2 text-[11px] text-muted/50 hover:text-muted transition-colors"
          >
            ✎ 編集 / Edit BIO
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <p className="text-sm text-muted/50 italic">No bio yet.</p>
          <button
            onClick={() => setMode("confirm")}
            className="text-[11px] text-muted/50 hover:text-muted transition-colors"
          >
            ✎ BIO を書く / Add BIO
          </button>
        </div>
      )}
    </div>
  );
}
