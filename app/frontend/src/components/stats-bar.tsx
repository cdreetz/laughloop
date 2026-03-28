import type { Stats } from "@/lib/api";

interface StatsBarProps {
  stats: Stats | null;
}

export function StatsBar({ stats }: StatsBarProps) {
  if (!stats) return null;

  return (
    <div className="flex items-center gap-4 border-b border-border-custom px-4 py-1.5 font-mono text-[11px] text-text-dim">
      <span>{stats.total_interactions} chats</span>
      <span>{stats.funny_count} laughs</span>
      <span>
        {(stats.haha_rate * 100).toFixed(0)}% haha rate
      </span>
      <span className="ml-auto">
        {stats.current_adapter !== "(base model)"
          ? `adapter: ${stats.current_adapter.slice(0, 8)}`
          : "base model"}
      </span>
    </div>
  );
}
