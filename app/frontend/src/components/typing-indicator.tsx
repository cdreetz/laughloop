export function TypingIndicator() {
  return (
    <div className="px-5 py-2">
      <div className="flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-1 w-1 rounded-full bg-text-dim"
            style={{
              animation: `bounce-dot 1.2s ease-in-out ${i * 0.15}s infinite`,
            }}
          />
        ))}
      </div>
    </div>
  );
}
