"use client";

import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { API_BASE_URL, type StrategyData } from "@/lib/api";
import { agentIconUrl, roleClasses } from "@/lib/agents";
import { mapThumbnailUrl, COMPETITIVE_MAPS } from "@/lib/maps";

type Props = {
  params: Promise<{ name: string; tag: string }>;
};

const STRATEGY_PLAYERS = ["Curush", "Syachi", "BABYNOYEN", "にょにょ", "Tigerin0", "lisbeth"];

type Season = "all" | "v26a3";

const SEASON_OPTIONS: { value: Season; label: string }[] = [
  { value: "all", label: "全体" },
  { value: "v26a3", label: "V26A3" },
];

// V26A3 schedule order (Split excluded per user request)
const V26A3_MAPS: string[] = ["Ascent", "Lotus", "Breeze", "Pearl", "Haven", "Fracture"];

const ROLE_GROUPS = [
  { label: "Duelist",    agents: ["Jett","Reyna","Raze","Phoenix","Neon","Yoru","Iso","Waylay"] },
  { label: "Initiator",  agents: ["Sova","Skye","Breach","KAY/O","Fade","Gekko","Tejo"] },
  { label: "Controller", agents: ["Brimstone","Omen","Viper","Astra","Harbor","Clove","Miks"] },
  { label: "Sentinel",   agents: ["Cypher","Killjoy","Sage","Chamber","Deadlock","Vyse","Veto"] },
];

export default function StrategyPage({ params }: Props) {
  const [name, setName] = useState("");
  const [tag, setTag] = useState("");
  const [comps, setComps] = useState<StrategyData>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [expanded, setExpanded] = useState<string | null>(null);
  const [season, setSeason] = useState<Season>("all");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    params.then(({ name: n, tag: t }) => {
      const dn = decodeURIComponent(n);
      const dt = decodeURIComponent(t);
      setName(dn);
      setTag(dt);
      fetch(`${API_BASE_URL}/api/teams/${encodeURIComponent(dn)}/${encodeURIComponent(dt)}/strategy`)
        .then((r) => r.json())
        .then((d) => {
          setComps(d.data ?? {});
          setNotes(d.notes ?? {});
        })
        .catch(() => {});
    });
  }, [params]);

  const scheduleSave = useCallback(
    (nextComps: StrategyData, nextNotes: Record<string, string>) => {
      if (!name || !tag) return;
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(() => {
        setSaving(true);
        setSaved(false);
        fetch(
          `${API_BASE_URL}/api/teams/${encodeURIComponent(name)}/${encodeURIComponent(tag)}/strategy`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ data: nextComps, notes: nextNotes }),
          },
        )
          .then(() => {
            setSaving(false);
            setSaved(true);
            setTimeout(() => setSaved(false), 2000);
          })
          .catch(() => setSaving(false));
      }, 800);
    },
    [name, tag],
  );

  const setAgent = (map: string, player: string, agent: string | null) => {
    const next: StrategyData = { ...comps, [map]: { ...(comps[map] ?? {}), [player]: agent } };
    setComps(next);
    scheduleSave(next, notes);
  };

  const setNote = (map: string, text: string) => {
    const next = { ...notes, [map]: text };
    setNotes(next);
    scheduleSave(comps, next);
  };

  const toggleExpand = (map: string) => {
    setExpanded((prev) => (prev === map ? null : map));
  };

  const visibleMaps = season === "v26a3" ? V26A3_MAPS : COMPETITIVE_MAPS;

  return (
    <div className="space-y-4">
      {/* Title + season selector + save status */}
      <div className="flex items-center gap-3">
        <h2 className="text-xs uppercase tracking-widest text-muted">Map Compositions</h2>

        {/* Season dropdown */}
        <div className="flex rounded-md border border-border overflow-hidden text-[11px] font-semibold uppercase tracking-wider">
          {SEASON_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setSeason(opt.value)}
              className={`px-3 py-1 transition-colors ${
                season === opt.value
                  ? "bg-accent text-bg-elevated"
                  : "text-muted hover:text-text hover:bg-bg-elevated"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <div className="ml-auto text-[11px]">
          {saving && <span className="text-muted">保存中…</span>}
          {saved && !saving && <span className="text-win">保存済み ✓</span>}
        </div>
      </div>

      {/* Sticky column header */}
      <div
        className="sticky top-[44px] z-20 rounded-t-md border border-border bg-bg-elevated px-4 py-2"
        style={{ display: "grid", gridTemplateColumns: "2rem 180px repeat(6, 1fr)" }}
      >
        <span />
        <span className="text-[11px] uppercase tracking-wider text-muted">Map</span>
        {STRATEGY_PLAYERS.map((p) => (
          <span key={p} className="text-[11px] uppercase tracking-wider text-muted text-center truncate px-1">
            {p}
          </span>
        ))}
      </div>

      {/* Map rows */}
      <div className="rounded-b-md border border-t-0 border-border divide-y divide-border/60">
        {visibleMaps.map((map, idx) => {
          const thumb = mapThumbnailUrl(map);
          const mapData = comps[map] ?? {};
          const isOpen = expanded === map;
          const hasNote = !!(notes[map]?.trim());
          const weekLabel = season === "v26a3" ? `Week ${String(idx + 1).padStart(2, "0")}` : null;

          return (
            <div key={map} className={idx % 2 === 0 ? "bg-panel" : "bg-bg-elevated/40"}>
              {/* Comp row */}
              <div
                className="grid items-center px-4 py-3 gap-x-2"
                style={{ gridTemplateColumns: "2rem 180px repeat(6, 1fr)" }}
              >
                {/* Expand toggle */}
                <button
                  onClick={() => toggleExpand(map)}
                  title={isOpen ? "閉じる" : "ノートを開く"}
                  className={`flex items-center justify-center w-6 h-6 rounded transition-colors ${
                    isOpen
                      ? "text-accent"
                      : hasNote
                        ? "text-muted-strong hover:text-text"
                        : "text-muted/30 hover:text-muted"
                  }`}
                >
                  <svg
                    viewBox="0 0 16 16"
                    fill="currentColor"
                    className={`w-3.5 h-3.5 transition-transform ${isOpen ? "rotate-90" : ""}`}
                  >
                    <path d="M6 3l5 5-5 5V3z" />
                  </svg>
                </button>

                {/* Map name + thumbnail */}
                <button
                  onClick={() => toggleExpand(map)}
                  className="flex items-center gap-3 text-left"
                >
                  {thumb && (
                    <Image
                      src={thumb}
                      alt={map}
                      width={48}
                      height={28}
                      className="rounded-sm object-cover opacity-80"
                    />
                  )}
                  <div>
                    {weekLabel && (
                      <p className="text-[10px] uppercase tracking-widest text-muted/60 leading-none mb-0.5">
                        {weekLabel}
                      </p>
                    )}
                    <span className="text-sm font-semibold text-text-strong hover:text-accent transition-colors">
                      {map}
                    </span>
                  </div>
                  {hasNote && !isOpen && (
                    <span className="text-[10px] text-muted/60 italic truncate max-w-[100px]">
                      {notes[map]!.split("\n")[0].slice(0, 30)}…
                    </span>
                  )}
                </button>

                {/* Agent selectors */}
                {STRATEGY_PLAYERS.map((player) => (
                  <AgentSelector
                    key={player}
                    value={mapData[player] ?? null}
                    onChange={(agent) => setAgent(map, player, agent)}
                  />
                ))}
              </div>

              {/* Expandable note */}
              {isOpen && (
                <div className="border-t border-border/60 bg-bg-elevated/30 px-6 py-4">
                  <MapNote
                    mapName={map}
                    value={notes[map] ?? ""}
                    onChange={(text) => setNote(map, text)}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Markdown-capable map note
// ---------------------------------------------------------------------------

function MapNote({
  mapName,
  value,
  onChange,
}: {
  mapName: string;
  value: string;
  onChange: (text: string) => void;
}) {
  const [preview, setPreview] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el || preview) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value, preview]);

  return (
    <div className="rounded-md border border-border overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-1 border-b border-border bg-bg-elevated px-3 py-1.5">
        <span className="text-[10px] uppercase tracking-widest text-muted mr-2">{mapName} Note</span>
        <div className="ml-auto">
          <button
            onClick={() => setPreview((v) => !v)}
            className={`rounded px-3 py-1 text-[11px] font-semibold uppercase tracking-wider transition-colors ${
              preview
                ? "bg-accent text-bg-elevated"
                : "border border-border text-muted hover:text-text"
            }`}
          >
            {preview ? "Edit" : "Preview"}
          </button>
        </div>
      </div>

      {/* Editor / Preview */}
      {preview ? (
        <div className="min-h-[80px] px-6 py-4 bg-bg prose-note overflow-auto">
          {value.trim() ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ children }) => <h1 className="text-xl font-bold text-text-strong mt-4 mb-2 first:mt-0">{children}</h1>,
                h2: ({ children }) => <h2 className="text-lg font-semibold text-text-strong mt-3 mb-1 border-b border-border pb-1">{children}</h2>,
                h3: ({ children }) => <h3 className="text-base font-semibold text-text-strong mt-3 mb-1">{children}</h3>,
                p: ({ children }) => <p className="text-sm text-text leading-relaxed mb-2">{children}</p>,
                ul: ({ children }) => <ul className="list-disc list-inside text-sm text-text space-y-1 mb-2 pl-2">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal list-inside text-sm text-text space-y-1 mb-2 pl-2">{children}</ol>,
                li: ({ children }) => <li className="text-sm text-text">{children}</li>,
                strong: ({ children }) => <strong className="font-semibold text-text-strong">{children}</strong>,
                em: ({ children }) => <em className="italic text-muted-strong">{children}</em>,
                blockquote: ({ children }) => <blockquote className="border-l-4 border-accent pl-4 my-2 text-sm text-muted italic">{children}</blockquote>,
                hr: () => <hr className="my-4 border-border" />,
                code: ({ inline, children, ...props }: { inline?: boolean; children?: React.ReactNode }) =>
                  inline ? (
                    <code className="rounded bg-bg-elevated px-1.5 py-0.5 font-mono text-xs text-accent" {...props}>{children}</code>
                  ) : (
                    <pre className="rounded-md bg-bg-elevated p-3 overflow-x-auto mb-2">
                      <code className="font-mono text-xs text-text-strong" {...props}>{children}</code>
                    </pre>
                  ),
              }}
            >
              {value}
            </ReactMarkdown>
          ) : (
            <p className="text-sm text-muted/50 italic">No note yet.</p>
          )}
        </div>
      ) : (
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={`${mapName} のスタッツ、立ち回り、対策など… (Markdown 対応)`}
          spellCheck={false}
          rows={4}
          className="w-full resize-none overflow-hidden bg-bg px-6 py-4 font-mono text-sm text-text leading-relaxed placeholder:text-muted/40 focus:outline-none"
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Agent selector cell
// ---------------------------------------------------------------------------

function AgentSelector({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (agent: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const iconUrl = agentIconUrl(value);
  const roleClass = value ? roleClasses(value) : "border-border/40 text-muted/40";

  return (
    <div ref={ref} className="relative flex justify-center">
      <button
        onClick={() => setOpen((v) => !v)}
        title={value ?? "未設定"}
        className={`flex flex-col items-center gap-1 rounded-md border px-1.5 py-1.5 w-full transition-colors hover:border-accent/60 ${roleClass}`}
      >
        {iconUrl ? (
          <Image src={iconUrl} alt={value!} width={28} height={28} className="rounded-sm" />
        ) : (
          <div className="w-7 h-7 rounded-sm bg-white/5 flex items-center justify-center">
            <span className="text-[10px] text-muted">?</span>
          </div>
        )}
        <span className="text-[10px] leading-tight truncate w-full text-center">
          {value ?? "—"}
        </span>
      </button>

      {open && (
        <div className="absolute top-full mt-1 z-50 w-52 rounded-md border border-border bg-panel shadow-lg overflow-y-auto max-h-80">
          <button
            className="w-full px-3 py-1.5 text-left text-[11px] text-muted hover:bg-bg-elevated transition-colors border-b border-border/60"
            onClick={() => { onChange(null); setOpen(false); }}
          >
            — 未設定
          </button>
          {ROLE_GROUPS.map((group) => (
            <div key={group.label}>
              <div className="px-3 py-1 text-[10px] uppercase tracking-wider text-muted/60 bg-bg-elevated/60">
                {group.label}
              </div>
              {group.agents.map((agent) => {
                const icon = agentIconUrl(agent);
                return (
                  <button
                    key={agent}
                    onClick={() => { onChange(agent); setOpen(false); }}
                    className={`w-full flex items-center gap-2 px-3 py-1.5 text-left text-[12px] hover:bg-bg-elevated transition-colors ${
                      value === agent ? "bg-accent/10 text-accent" : "text-text"
                    }`}
                  >
                    {icon && (
                      <Image src={icon} alt={agent} width={20} height={20} className="rounded-sm shrink-0" />
                    )}
                    <span>{agent}</span>
                    {value === agent && <span className="ml-auto text-accent text-[10px]">✓</span>}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
