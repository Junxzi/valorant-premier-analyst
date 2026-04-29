import Image from "next/image";
import Link from "next/link";

import { SyncButton } from "@/components/SyncButton";

export function Header() {
  const defaultName = process.env.DEFAULT_TEAM_NAME ?? "";
  const defaultTag = process.env.DEFAULT_TEAM_TAG ?? "";
  const teamHref =
    defaultName && defaultTag
      ? `/team/${encodeURIComponent(defaultName)}/${encodeURIComponent(defaultTag)}`
      : "/";

  return (
    <header className="sticky top-0 z-10 border-b border-border bg-bg/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <Link href={teamHref} className="flex items-center gap-2 group">
          <Image
            src="/logo.png"
            alt="120ping-FTW"
            width={28}
            height={28}
            className="rounded-sm"
          />
          <span className="text-sm font-semibold tracking-wide text-text-strong">
            120ping-FTW
          </span>
        </Link>
        <nav className="flex items-center gap-5 text-xs uppercase tracking-wider text-muted">
          <Link className="hover:text-text" href={teamHref}>
            Home
          </Link>
          <SyncButton />
          <a
            className="hover:text-text"
            href={`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"}/docs`}
            target="_blank"
            rel="noopener noreferrer"
          >
            API
          </a>
        </nav>
      </div>
    </header>
  );
}
