"use client";

import { motion } from "framer-motion";
import { cn, riskColorClass, type RiskLevel } from "@/lib/utils";
import { AlertTriangle, CheckCircle2, AlertCircle, HelpCircle } from "lucide-react";

interface RiskBadgeProps {
  level: RiskLevel;
  size?: "sm" | "md" | "lg";
  className?: string;
  showLabel?: boolean;
}

const labelMap: Record<RiskLevel, string> = {
  low: "低風險",
  medium: "中風險",
  high: "高風險",
  unknown: "未判定",
};

const iconMap: Record<RiskLevel, React.ComponentType<{ className?: string }>> = {
  low: CheckCircle2,
  medium: AlertCircle,
  high: AlertTriangle,
  unknown: HelpCircle,
};

export function RiskBadge({
  level,
  size = "md",
  className,
  showLabel = true,
}: RiskBadgeProps) {
  const Icon = iconMap[level];
  const sizeClass =
    size === "sm"
      ? "px-2.5 py-0.5 text-xs gap-1"
      : size === "lg"
        ? "px-4 py-1.5 text-base gap-2"
        : "px-3 py-1 text-sm gap-1.5";
  return (
    <motion.span
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: "spring", stiffness: 300, damping: 18 }}
      className={cn(
        "inline-flex items-center rounded-full border font-display font-medium",
        riskColorClass(level),
        sizeClass,
        className,
      )}
    >
      <Icon className={cn(size === "sm" ? "h-3 w-3" : "h-4 w-4")} />
      {showLabel && labelMap[level]}
    </motion.span>
  );
}
