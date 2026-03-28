"use client";

interface HeaderProps {
  onNewChat: () => void;
}

export function Header({ onNewChat }: HeaderProps) {
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
      <div className="ml-auto">
        <button
          onClick={onNewChat}
          className="cursor-pointer rounded border border-border-custom px-3 py-1 font-mono text-[11px] text-text-dim transition-colors hover:border-foreground hover:text-foreground"
        >
          New Chat
        </button>
      </div>
    </div>
  );
}
