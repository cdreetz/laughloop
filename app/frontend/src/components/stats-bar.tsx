import type { Stats } from "@/lib/api";

interface StatsBarProps {
  stats: Stats | null;
}

export function StatsBar({ stats }: StatsBarProps) {
  if (!stats) return null;

  return (
    <div className="flex flex-wrap items-center gap-4 border-b border-border-custom bg-surface px-4 py-2 font-mono text-xs text-text-dim">
      <span>
        <strong className="text-foreground">{stats.total_interactions}</strong>{" "}
        chats
      </span>
      <span>
        <strong className="text-funny">{stats.funny_count}</strong> laughs
      </span>
      <span>
        Haha rate:{" "}
        <strong
          className={
            stats.haha_rate > 0.5 ? "text-funny" : "text-accent"
          }
        >
          {(stats.haha_rate * 100).toFixed(1)}%
        </strong>
      </span>
      <span className="ml-auto opacity-60">
        {stats.current_adapter !== "(base model)"
          ? `adapter: ${stats.current_adapter.slice(0, 8)}...`
          : "base model"}
      </span>
    </div>
  );
}
