"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { ScrollText } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface CitationChipProps {
  article: string;
  detail?: string;
  matched?: boolean;
  className?: string;
}

export function CitationChip({
  article,
  detail,
  matched = true,
  className,
}: CitationChipProps) {
  const chip = (
    <motion.span
      whileHover={{ y: -1 }}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5",
        "font-mono text-xs font-medium",
        matched
          ? "bg-candy-lavender-100 text-candy-lavender-500 border-candy-lavender-300"
          : "bg-candy-coral-100 text-candy-coral-500 border-candy-coral-300",
        "cursor-help shadow-sm",
        className,
      )}
    >
      <ScrollText className="h-3 w-3" />
      {article}
    </motion.span>
  );

  if (!detail) return chip;

  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild>{chip}</TooltipTrigger>
        <TooltipContent
          side="top"
          className="max-w-sm whitespace-pre-wrap text-sm leading-relaxed"
        >
          {detail}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
