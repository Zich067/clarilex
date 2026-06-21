"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface ScoreGaugeProps {
  value: number;        // 0-1
  label: string;
  size?: number;        // px
  tint?: "pink" | "mint" | "lavender" | "sky" | "coral" | "lemon";
  formatter?: (v: number) => string;
}

const tintGradient: Record<NonNullable<ScoreGaugeProps["tint"]>, string> = {
  pink: "from-candy-pink-300 to-candy-pink-500",
  mint: "from-candy-mint-300 to-candy-mint-500",
  lavender: "from-candy-lavender-300 to-candy-lavender-500",
  sky: "from-candy-sky-300 to-candy-sky-500",
  coral: "from-candy-coral-300 to-candy-coral-500",
  lemon: "from-candy-lemon-300 to-candy-lemon-500",
};

const tintStroke: Record<NonNullable<ScoreGaugeProps["tint"]>, string> = {
  pink: "#ff8fc2",
  mint: "#5ec99f",
  lavender: "#9670ec",
  sky: "#5fb0ee",
  coral: "#ee5c69",
  lemon: "#f5c451",
};

export function ScoreGauge({
  value,
  label,
  size = 120,
  tint = "lavender",
  formatter = (v) => (v * 100).toFixed(0) + "%",
}: ScoreGaugeProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const stroke = tintStroke[tint];
  const radius = size / 2 - 10;
  const circ = 2 * Math.PI * radius;
  const dash = circ * (1 - clamped);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(255, 241, 247, 1)"
            strokeWidth={10}
          />
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={stroke}
            strokeWidth={10}
            strokeLinecap="round"
            strokeDasharray={circ}
            initial={{ strokeDashoffset: circ }}
            animate={{ strokeDashoffset: dash }}
            transition={{ duration: 1.2, ease: "easeOut" }}
          />
        </svg>
        <div
          className={cn(
            "absolute inset-0 flex items-center justify-center",
            "bg-gradient-to-br bg-clip-text text-transparent font-display font-bold text-2xl",
            tintGradient[tint],
          )}
        >
          {formatter(clamped)}
        </div>
      </div>
      <span className="font-display text-sm text-candy-mocha">{label}</span>
    </div>
  );
}
