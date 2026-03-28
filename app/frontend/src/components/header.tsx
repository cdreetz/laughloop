"use client";

interface HeaderProps {
  onNewChat: () => void;
}

export function Header({ onNewChat }: HeaderProps) {
  return (
    <div className="flex items-center gap-3 border-b border-border-custom bg-surface px-5 py-4">
      <div
        className="text-3xl leading-none"
        style={{ animation: "bounce-dot 2s ease-in-out infinite" }}
      >
        {"\uD83C\uDFAA"}
      </div>
      <div>
        <h1
          className="font-[family-name:var(--font-playfair)] text-xl font-black leading-tight"
          style={{
            background: "linear-gradient(135deg, #f5c542, #ff6b6b, #f5c542)",
            backgroundSize: "200% 200%",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            animation: "gradient-shift 4s ease infinite",
          }}
        >
          LaughLoop
        </h1>
        <p className="mt-0.5 font-mono text-[11px] tracking-wider text-text-dim">
          CONTINUAL LEARNING COMEDY AI \u2014 GETS FUNNIER OVER TIME
        </p>
      </div>
      <div className="ml-auto flex gap-2">
        <button
          onClick={onNewChat}
          className="cursor-pointer rounded-lg border border-border-custom bg-transparent px-3.5 py-1.5 font-mono text-xs text-text-dim transition-all duration-200 hover:border-accent hover:text-accent"
        >
          New Chat
        </button>
      </div>
    </div>
  );
}
