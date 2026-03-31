"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface HeaderProps {
  onNewChat?: () => void;
}

export function Header({ onNewChat }: HeaderProps) {
  const pathname = usePathname();

  return (
    <div className="flex items-center gap-3 border-b border-border-custom bg-surface px-5 py-3">
      <div>
        <h1 className="text-sm font-semibold tracking-tight text-foreground">
          LaughLoop
        </h1>
        <p className="font-mono text-[10px] tracking-wide text-text-dim">
          online learning demo
        </p>
      </div>
      <nav className="ml-6 flex gap-1">
        <Link
          href="/"
          className={`rounded px-3 py-1 font-mono text-[11px] transition-colors ${
            pathname === "/"
              ? "bg-foreground/5 font-medium text-foreground"
              : "text-text-dim hover:bg-black/5 hover:text-foreground"
          }`}
        >
          Chat
        </Link>
        <Link
          href="/evals"
          className={`rounded px-3 py-1 font-mono text-[11px] transition-colors ${
            pathname === "/evals"
              ? "bg-foreground/5 font-medium text-foreground"
              : "text-text-dim hover:bg-black/5 hover:text-foreground"
          }`}
        >
          Evals
        </Link>
        <Link
          href="/admin"
          className={`rounded px-3 py-1 font-mono text-[11px] transition-colors ${
            pathname === "/admin"
              ? "bg-foreground/5 font-medium text-foreground"
              : "text-text-dim hover:bg-black/5 hover:text-foreground"
          }`}
        >
          Admin
        </Link>
      </nav>
      <div className="ml-auto">
        {onNewChat && (
          <button
            onClick={onNewChat}
            className="cursor-pointer rounded border border-border-custom px-3 py-1 font-mono text-[11px] text-text-dim transition-colors hover:border-foreground hover:text-foreground"
          >
            New Chat
          </button>
        )}
      </div>
    </div>
  );
}
