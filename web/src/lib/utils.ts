import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** shadcn-style class composer */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export type RiskLevel = "low" | "medium" | "high" | "unknown";

export function formatScore(n: number, digits = 2): string {
  if (Number.isNaN(n) || !Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

export function riskColorClass(level: RiskLevel): string {
  switch (level) {
    case "low":
      return "bg-candy-mint-200 text-candy-mint-500 border-candy-mint-300";
    case "medium":
      return "bg-candy-lemon-100 text-candy-lemon-500 border-candy-lemon-300";
    case "high":
      return "bg-candy-coral-100 text-candy-coral-500 border-candy-coral-300";
    default:
      return "bg-candy-lavender-100 text-candy-lavender-500 border-candy-lavender-300";
  }
}
