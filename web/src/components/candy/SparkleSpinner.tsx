"use client";

import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export function SparkleSpinner({
  label,
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, duration: 2.5, ease: "linear" }}
        className="rounded-full candy-gradient p-2 shadow-[0_8px_24px_rgba(255,182,217,0.45)]"
      >
        <Sparkles className="h-5 w-5 text-white" />
      </motion.div>
      {label && (
        <motion.span
          animate={{ opacity: [0.6, 1, 0.6] }}
          transition={{ repeat: Infinity, duration: 1.6 }}
          className="font-display text-candy-mocha"
        >
          {label}
        </motion.span>
      )}
    </div>
  );
}
