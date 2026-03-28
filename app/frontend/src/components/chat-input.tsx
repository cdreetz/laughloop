"use client";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  loading: boolean;
}

export function ChatInput({ value, onChange, onSend, loading }: ChatInputProps) {
  return (
    <div className="border-t border-border-custom px-4 py-3">
      <div className="flex gap-2">
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSend();
            }
          }}
          placeholder="Type a message..."
          className="flex-1 rounded border border-border-custom bg-surface px-3 py-2 text-sm text-foreground focus:border-foreground focus:outline-none"
        />
        <button
          onClick={onSend}
          disabled={loading || !value.trim()}
          className="rounded bg-foreground px-4 py-2 text-sm font-medium text-surface enabled:cursor-pointer disabled:cursor-not-allowed disabled:opacity-30"
        >
          {loading ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}
