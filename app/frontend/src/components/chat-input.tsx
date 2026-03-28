"use client";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  loading: boolean;
}

export function ChatInput({ value, onChange, onSend, loading }: ChatInputProps) {
  return (
    <div className="border-t border-border-custom bg-surface px-4 py-3">
      <div className="mx-auto flex max-w-2xl gap-2">
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSend();
            }
          }}
          placeholder="Say something... I'll try to make it funny"
          className="flex-1 rounded-xl border border-border-custom bg-background px-4 py-3 text-sm text-foreground transition-colors duration-200 focus:border-accent focus:outline-none"
        />
        <button
          onClick={onSend}
          disabled={loading || !value.trim()}
          className="rounded-xl border-none bg-accent px-5 py-3 text-sm font-bold text-background transition-all duration-200 enabled:cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "..." : "Send"}
        </button>
      </div>
      <p className="mt-2 text-center font-mono text-[11px] text-text-dim">
        Your feedback trains the model in real-time via reinforcement learning
      </p>
    </div>
  );
}
