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
      <div className="text-6xl">{"\uD83C\uDFAD"}</div>
      <h2 className="font-[family-name:var(--font-playfair)] text-2xl font-bold text-foreground">
        Ready to laugh?
      </h2>
      <p className="max-w-sm text-sm leading-relaxed text-text-dim">
        Say anything. I&apos;ll try to make it funny.
        <br />
        Click{" "}
        <strong className="text-funny">Haha</strong> if I
        land the joke \u2014 it helps me learn!
      </p>
      <div className="mt-2 flex flex-wrap justify-center gap-2">
        {PROMPTS.map((prompt) => (
          <button
            key={prompt}
            onClick={() => onSelectPrompt(prompt)}
            className="cursor-pointer rounded-full border border-border-custom bg-surface px-4 py-2 text-xs text-text-dim transition-all duration-200 hover:border-accent hover:bg-accent-glow hover:text-accent"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
