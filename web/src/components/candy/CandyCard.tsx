"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import { forwardRef } from "react";
import { cn } from "@/lib/utils";

interface CandyCardProps extends Omit<HTMLMotionProps<"div">, "ref"> {
  tint?: "pink" | "mint" | "lemon" | "lavender" | "sky" | "coral" | "plain";
  glow?: boolean;
  interactive?: boolean;
}

const tintMap: Record<NonNullable<CandyCardProps["tint"]>, string> = {
  pink: "bg-candy-pink-100/70 border-candy-pink-200/60",
  mint: "bg-candy-mint-100/70 border-candy-mint-200/60",
  lemon: "bg-candy-lemon-100/70 border-candy-lemon-300/40",
  lavender: "bg-candy-lavender-100/70 border-candy-lavender-300/40",
  sky: "bg-candy-sky-100/70 border-candy-sky-300/40",
  coral: "bg-candy-coral-100/70 border-candy-coral-300/40",
  plain: "glass",
};

export const CandyCard = forwardRef<HTMLDivElement, CandyCardProps>(
  function CandyCard(
    { tint = "plain", glow = false, interactive = false, className, children, ...rest },
    ref,
  ) {
    return (
      <motion.div
        ref={ref}
        whileHover={interactive ? { y: -3, scale: 1.005 } : undefined}
        transition={{ type: "spring", stiffness: 260, damping: 22 }}
        className={cn(
          "relative rounded-3xl border p-5 transition-shadow",
          tintMap[tint],
          glow && "shadow-[0_8px_30px_rgba(255,182,217,0.25)]",
          interactive && "cursor-pointer hover:shadow-[0_16px_50px_rgba(255,182,217,0.35)]",
          className,
        )}
        {...rest}
      >
        {children}
      </motion.div>
    );
  },
);
