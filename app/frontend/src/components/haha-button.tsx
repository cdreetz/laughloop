"use client";

import { useState } from "react";
import { sendFeedback } from "@/lib/api";

interface HahaButtonProps {
  interactionId: string;
  onFeedback: () => void;
}

type FeedbackState = "idle" | "funny" | "notFunny";

export function HahaButton({ interactionId, onFeedback }: HahaButtonProps) {
  const [state, setState] = useState<FeedbackState>("idle");

  const handleFunny = async () => {
    setState("funny");
    onFeedback();
    try {
      await sendFeedback({ interaction_id: interactionId, funny: true });
    } catch (e) {
      console.error("Feedback failed:", e);
    }
  };

  const handleNotFunny = async () => {
    setState("notFunny");
    onFeedback();
    try {
      await sendFeedback({ interaction_id: interactionId, funny: false });
    } catch (e) {
      console.error("Feedback failed:", e);
    }
  };

  if (state === "funny") {
    return (
      <span className="font-mono text-[11px] text-funny">
        haha
      </span>
    );
  }

  if (state === "notFunny") {
    return (
      <span className="font-mono text-[11px] text-not-funny">
        meh
      </span>
    );
  }

  return (
    <div className="flex gap-2">
      <button
        onClick={handleFunny}
        className="cursor-pointer font-mono text-[11px] text-text-dim transition-colors hover:text-funny"
      >
        haha
      </button>
      <button
        onClick={handleNotFunny}
        className="cursor-pointer font-mono text-[11px] text-text-dim transition-colors hover:text-not-funny"
      >
        meh
      </button>
    </div>
  );
}
