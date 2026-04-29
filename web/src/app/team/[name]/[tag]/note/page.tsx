"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { API_BASE_URL } from "@/lib/api";

type Props = {
  params: Promise<{ name: string; tag: string }>;
};

export default function NotePage({ params }: Props) {
  const [name, setName] = useState("");
  const [tag, setTag] = useState("");
  const [content, setContent] = useState("");
  const [preview, setPreview] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    params.then(({ name: n, tag: t }) => {
      const dn = decodeURIComponent(n);
      const dt = decodeURIComponent(t);
      setName(dn);
      setTag(dt);
      fetch(
        `${API_BASE_URL}/api/teams/${encodeURIComponent(dn)}/${encodeURIComponent(dt)}/note`,
      )
        .then((r) => r.json())
        .then((d) => setContent(d.content ?? ""))
        .catch(() => {});
    });
  }, [params]);

  const save = useCallback(
    (text: string) => {
      if (!name || !tag) return;
      setSaving(true);
      setSaved(false);
      fetch(
        `${API_BASE_URL}/api/teams/${encodeURIComponent(name)}/${encodeURIComponent(tag)}/note`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: text }),
        },
      )
        .then(() => {
          setSaving(false);
          setSaved(true);
          setTimeout(() => setSaved(false), 2000);
        })
        .catch(() => setSaving(false));
    },
    [name, tag],
  );

  const handleChange = (text: string) => {
    setContent(text);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => save(text), 1200);
  };

  const insertAt = (before: string, after = "", placeholder = "") => {
    const el = textareaRef.current;
    if (!el) return;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const selected = content.slice(start, end) || placeholder;
    const next =
      content.slice(0, start) + before + selected + after + content.slice(end);
    handleChange(next);
    setTimeout(() => {
      el.focus();
      const cur = start + before.length + selected.length;
      el.setSelectionRange(cur, cur);
    }, 0);
  };

  const tools: { label: string; title: string; action: () => void }[] = [
    {
      label: "H1",
      title: "Heading 1",
      action: () => insertAt("# ", "", "Heading"),
    },
    {
      label: "H2",
      title: "Heading 2",
      action: () => insertAt("## ", "", "Heading"),
    },
    {
      label: "H3",
      title: "Heading 3",
      action: () => insertAt("### ", "", "Heading"),
    },
    { label: "B", title: "Bold", action: () => insertAt("**", "**", "bold") },
    {
      label: "I",
      title: "Italic",
      action: () => insertAt("_", "_", "italic"),
    },
    {
      label: "~~",
      title: "Strikethrough",
      action: () => insertAt("~~", "~~", "text"),
    },
    {
      label: "—",
      title: "Divider",
      action: () => insertAt("\n\n---\n\n", "", ""),
    },
    {
      label: "• List",
      title: "Bullet list",
      action: () => insertAt("- ", "", "item"),
    },
    {
      label: "1. List",
      title: "Ordered list",
      action: () => insertAt("1. ", "", "item"),
    },
    {
      label: "[ ] Todo",
      title: "Checkbox",
      action: () => insertAt("- [ ] ", "", "task"),
    },
    {
      label: "`Code`",
      title: "Inline code",
      action: () => insertAt("`", "`", "code"),
    },
    {
      label: "```Block",
      title: "Code block",
      action: () => insertAt("```\n", "\n```", "code"),
    },
    {
      label: "> Quote",
      title: "Blockquote",
      action: () => insertAt("> ", "", "quote"),
    },
    {
      label: "| Table",
      title: "Insert table",
      action: () =>
        insertAt(
          "\n| Column 1 | Column 2 | Column 3 |\n| --- | --- | --- |\n| ",
          " | | |\n",
          "value",
        ),
    },
  ];

  return (
    <div className="rounded-md border border-border bg-panel overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-1 flex-wrap border-b border-border bg-bg-elevated px-3 py-1.5">
        {tools.map((t) => (
          <button
            key={t.label}
            title={t.title}
            onClick={t.action}
            disabled={preview}
            className="rounded px-2 py-0.5 text-[11px] font-mono font-semibold text-muted hover:bg-panel hover:text-text disabled:opacity-30 transition-colors"
          >
            {t.label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          {saving && (
            <span className="text-[11px] text-muted">保存中…</span>
          )}
          {saved && !saving && (
            <span className="text-[11px] text-win">保存済み ✓</span>
          )}
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
        <div className="min-h-[60vh] px-8 py-6 prose-note overflow-auto">
          {content.trim() ? (
            <MarkdownBody content={content} />
          ) : (
            <p className="text-muted italic text-sm">No content yet.</p>
          )}
        </div>
      ) : (
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => handleChange(e.target.value)}
          spellCheck={false}
          placeholder={`# ${name}#${tag} ノート\n\nここにメモ、戦術、スカウティングなどを自由に書けます。\nMarkdown に対応しています。`}
          className="w-full min-h-[60vh] resize-none bg-transparent px-8 py-6 font-mono text-sm text-text leading-relaxed placeholder:text-muted/50 focus:outline-none"
        />
      )}
    </div>
  );
}

function MarkdownBody({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => (
          <h1 className="text-2xl font-bold text-text-strong mt-8 mb-3 first:mt-0">
            {children}
          </h1>
        ),
        h2: ({ children }) => (
          <h2 className="text-xl font-semibold text-text-strong mt-6 mb-2 border-b border-border pb-1">
            {children}
          </h2>
        ),
        h3: ({ children }) => (
          <h3 className="text-base font-semibold text-text-strong mt-5 mb-2">
            {children}
          </h3>
        ),
        p: ({ children }) => (
          <p className="text-sm text-text leading-relaxed mb-3">{children}</p>
        ),
        ul: ({ children }) => (
          <ul className="list-disc list-inside text-sm text-text space-y-1 mb-3 pl-2">
            {children}
          </ul>
        ),
        ol: ({ children }) => (
          <ol className="list-decimal list-inside text-sm text-text space-y-1 mb-3 pl-2">
            {children}
          </ol>
        ),
        li: ({ children }) => <li className="text-sm text-text">{children}</li>,
        blockquote: ({ children }) => (
          <blockquote className="border-l-4 border-accent pl-4 my-3 text-sm text-muted italic">
            {children}
          </blockquote>
        ),
        code: ({ inline, children, ...props }: { inline?: boolean; children?: React.ReactNode }) =>
          inline ? (
            <code
              className="rounded bg-bg-elevated px-1.5 py-0.5 font-mono text-xs text-accent"
              {...props}
            >
              {children}
            </code>
          ) : (
            <pre className="rounded-md bg-bg-elevated p-4 overflow-x-auto mb-3">
              <code className="font-mono text-xs text-text-strong" {...props}>
                {children}
              </code>
            </pre>
          ),
        hr: () => <hr className="my-6 border-border" />,
        strong: ({ children }) => (
          <strong className="font-semibold text-text-strong">{children}</strong>
        ),
        em: ({ children }) => (
          <em className="italic text-muted-strong">{children}</em>
        ),
        table: ({ children }) => (
          <div className="overflow-x-auto mb-4">
            <table className="min-w-full text-sm border border-border rounded-md overflow-hidden">
              {children}
            </table>
          </div>
        ),
        thead: ({ children }) => (
          <thead className="bg-bg-elevated text-[11px] uppercase tracking-wider text-muted">
            {children}
          </thead>
        ),
        th: ({ children }) => (
          <th className="px-3 py-2 text-left font-semibold border-b border-border">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="px-3 py-2 border-b border-border/60 text-text">
            {children}
          </td>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
