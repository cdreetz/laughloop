"use client";

import { useEffect, useState } from "react";
import { fetchInteractions, type Interaction } from "@/lib/api";

interface LogViewerProps {
  refreshKey: number;
}

function formatTime(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function FeedbackBadge({ feedback }: { feedback: number | null }) {
  if (feedback === 1) {
    return (
      <span className="inline-flex items-center rounded-full bg-funny-glow px-2 py-0.5 text-[10px] font-semibold text-funny">
        HAHA
      </span>
    );
  }
  if (feedback === 0) {
    return (
      <span className="inline-flex items-center rounded-full bg-not-funny-glow px-2 py-0.5 text-[10px] font-semibold text-not-funny">
        MEH
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full border border-border-custom px-2 py-0.5 text-[10px] text-text-dim">
      PENDING
    </span>
  );
}

function ExportBadge({ exported }: { exported: number }) {
  if (exported === 1) {
    return (
      <span className="text-[10px] text-text-dim opacity-50">exported</span>
    );
  }
  return null;
}

export function LogViewer({ refreshKey }: LogViewerProps) {
  const [interactions, setInteractions] = useState<Interaction[]>([]);
  const [total, setTotal] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const data = await fetchInteractions(50);
        if (active) {
          setInteractions(data.interactions);
          setTotal(data.total);
        }
      } catch {
        // Non-critical
      }
    };
    load();
    const interval = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [refreshKey]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border-custom px-3 py-2">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-funny animate-pulse" />
          <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-text-dim">
            Interaction Log
          </h3>
        </div>
        <span className="font-mono text-[10px] text-text-dim">
          {total} entries
        </span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {interactions.length === 0 ? (
          <div className="flex h-full items-center justify-center p-4">
            <p className="text-center font-mono text-xs text-text-dim">
              No interactions yet.
              <br />
              Send a message to see log entries appear here.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-border-custom">
            {interactions.map((ix) => (
              <button
                key={ix.id}
                onClick={() =>
                  setExpanded(expanded === ix.id ? null : ix.id)
                }
                className="w-full cursor-pointer px-3 py-2 text-left transition-colors hover:bg-surface"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] text-text-dim">
                        {formatTime(ix.timestamp)}
                      </span>
                      <FeedbackBadge feedback={ix.feedback} />
                      <ExportBadge exported={ix.exported} />
                    </div>
                    <p className="mt-1 truncate text-xs text-foreground">
                      <span className="text-accent">Q:</span>{" "}
                      {ix.user_message}
                    </p>
                    {expanded === ix.id ? (
                      <div className="mt-2 space-y-1.5">
                        <p className="whitespace-pre-wrap text-xs leading-relaxed text-text-dim">
                          <span className="text-funny">A:</span>{" "}
                          {ix.assistant_message}
                        </p>
                        <div className="flex flex-wrap gap-2 font-mono text-[10px] text-text-dim">
                          <span>id: {ix.id.slice(0, 8)}</span>
                          <span>session: {ix.session_id.slice(0, 8)}</span>
                          <span>model: {ix.model}</span>
                          {ix.adapter_id && (
                            <span>adapter: {ix.adapter_id.slice(0, 8)}</span>
                          )}
                        </div>
                      </div>
                    ) : (
                      <p className="mt-0.5 truncate text-xs text-text-dim">
                        <span className="text-funny">A:</span>{" "}
                        {ix.assistant_message}
                      </p>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
