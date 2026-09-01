"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import { forwardRef } from "react";
import { cn } from "@/lib/utils";

interface GradientButtonProps
  extends Omit<HTMLMotionProps<"button">, "ref"> {
  variant?: "candy" | "warm" | "cool" | "fresh" | "ghost";
  size?: "sm" | "md" | "lg";
}

const variantMap: Record<NonNullable<GradientButtonProps["variant"]>, string> = {
  candy: "candy-gradient text-white shadow-[0_8px_24px_rgba(197,163,255,0.45)]",
  warm: "candy-gradient-warm text-candy-cocoa shadow-[0_8px_24px_rgba(255,227,158,0.5)]",
  cool: "candy-gradient-cool text-white shadow-[0_8px_24px_rgba(164,216,255,0.5)]",
  fresh: "candy-gradient-fresh text-candy-cocoa shadow-[0_8px_24px_rgba(168,230,207,0.5)]",
  ghost: "bg-white/70 backdrop-blur-md text-candy-cocoa border border-candy-pink-200/60",
};

const sizeMap: Record<NonNullable<GradientButtonProps["size"]>, string> = {
  sm: "px-4 py-2 text-sm",
  md: "px-6 py-2.5 text-base",
  lg: "px-8 py-3.5 text-lg",
};

export const GradientButton = forwardRef<
  HTMLButtonElement,
  GradientButtonProps
>(function GradientButton(
  { variant = "candy", size = "md", className, children, ...rest },
  ref,
) {
  return (
    <motion.button
      ref={ref}
      whileHover={{ y: -2, scale: 1.02 }}
      whileTap={{ scale: 0.97 }}
      transition={{ type: "spring", stiffness: 380, damping: 18 }}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full font-medium",
        "font-display tracking-wide",
        "transition-shadow",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        variantMap[variant],
        sizeMap[size],
        className,
      )}
      {...rest}
    >
      {children}
    </motion.button>
  );
});
