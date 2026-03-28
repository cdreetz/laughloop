"use client";

const PROMPTS = [
  "Tell me a joke",
  "Explain quantum physics",
  "What\u2019s for dinner?",
  "Roast my code",
];

interface EmptyStateProps {
  onSelectPrompt: (prompt: string) => void;
}

export function EmptyState({ onSelectPrompt }: EmptyStateProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-10 text-center">
      <h2 className="text-lg font-medium text-foreground">
        Ask me anything
      </h2>
      <p className="max-w-sm text-sm leading-relaxed text-text-dim">
        Rate responses with Haha or Meh to generate training data.
      </p>
      <div className="mt-2 flex flex-wrap justify-center gap-2">
        {PROMPTS.map((prompt) => (
          <button
            key={prompt}
            onClick={() => onSelectPrompt(prompt)}
            className="cursor-pointer rounded border border-border-custom px-3 py-1.5 text-xs text-text-dim transition-colors hover:border-foreground hover:text-foreground"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
