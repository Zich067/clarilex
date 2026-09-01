"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { AnalysisMode } from "@/lib/api";
import { useAnalyzeStore } from "@/lib/store";

const MODES: Array<{
  value: AnalysisMode;
  label: string;
  desc: string;
  activeBg: string;
  activeText: string;
}> = [
  {
    value: "baseline",
    label: "Baseline",
    desc: "純 LLM · 無 RAG",
    activeBg: "bg-candy-coral-200",
    activeText: "text-candy-coral-500",
  },
  {
    value: "rag",
    label: "RAG",
    desc: "向量檢索 + IRAC",
    activeBg: "bg-candy-lemon-200",
    activeText: "text-candy-lemon-500",
  },
  {
    value: "triangulation",
    label: "Triangulation",
    desc: "雙索引交叉佐證",
    activeBg: "bg-candy-mint-200",
    activeText: "text-candy-mint-500",
  },
];

export function ModeSwitch() {
  const { mode, setMode, isAnalyzing } = useAnalyzeStore();
  return (
    <div className="flex flex-col gap-1.5">
      <span className="px-1 font-display text-xs text-candy-mocha">分析模式</span>
      <div className="flex gap-1 rounded-full border border-candy-pink-200/40 bg-white/60 p-1 backdrop-blur-md">
        {MODES.map((m) => {
          const active = m.value === mode;
          return (
            <motion.button
              key={m.value}
              type="button"
              onClick={() => setMode(m.value)}
              disabled={isAnalyzing}
              whileTap={isAnalyzing ? undefined : { scale: 0.96 }}
              animate={{
                backgroundColor: active
                  ? m.value === "baseline"
                    ? "rgba(255, 184, 189, 1)"
                    : m.value === "rag"
                      ? "rgba(255, 232, 173, 1)"
                      : "rgba(196, 240, 217, 1)"
                  : "rgba(255, 255, 255, 0)",
              }}
              transition={{ duration: 0.18 }}
              className={cn(
                "flex-1 rounded-full px-3 py-1.5 text-xs font-display transition-colors",
                active ? "text-candy-cocoa" : "text-candy-mocha hover:text-candy-cocoa",
                isAnalyzing && "opacity-60 cursor-not-allowed",
              )}
              title={m.desc}
            >
              {m.label}
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
