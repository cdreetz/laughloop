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
      <div className="inline-flex items-center gap-1.5 rounded-full border border-funny bg-funny-glow px-3 py-1 text-xs font-semibold text-funny animate-[pop-in_0.3s_ease-out]">
        Haha!
      </div>
    );
  }

  if (state === "notFunny") {
    return (
      <div className="inline-flex items-center gap-1.5 rounded-full border border-not-funny bg-not-funny-glow px-3 py-1 text-xs font-semibold text-not-funny">
        Noted
      </div>
    );
  }

  return (
    <div className="flex gap-1.5 mt-1.5">
      <button
        onClick={handleFunny}
        className="inline-flex items-center gap-1 rounded-full border border-border-custom bg-transparent px-3.5 py-1 text-xs text-text-dim font-sans transition-all duration-200 hover:border-funny hover:text-funny hover:bg-funny-glow cursor-pointer"
      >
        Haha
      </button>
      <button
        onClick={handleNotFunny}
        className="inline-flex items-center gap-1 rounded-full border border-border-custom bg-transparent px-3.5 py-1 text-xs text-text-dim font-sans transition-all duration-200 hover:border-not-funny hover:text-not-funny hover:bg-not-funny-glow cursor-pointer"
      >
        Meh
      </button>
    </div>
  );
}
