"use client";

import { useEffect } from "react";
import { motion } from "framer-motion";
import { Wifi, WifiOff, Zap, Cookie } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAnalyzeStore } from "@/lib/store";
import { cn } from "@/lib/utils";

/**
 * 顯示 backend 連線狀態:
 * - live:  有 OPENAI_API_KEY,真實 GPT-4o
 * - mock:  backend 在,但無 API key 走 mock fallback
 * - down:  backend 沒起來,前端只能顯示 mock 預設資料
 */
export function BackendStatus({ compact = false }: { compact?: boolean }) {
  const { setBackendStatus, backendStatus, modelName } = useAnalyzeStore();
  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 15_000,
    retry: false,
  });

  useEffect(() => {
    if (isError) {
      setBackendStatus("down");
    } else if (data) {
      setBackendStatus(data.mock ? "mock" : "live", data.model);
    }
  }, [data, isError, setBackendStatus]);

  const prettyModel = modelName
    ? modelName.replace(/^gpt-/, "GPT-").replace(/-mini$/, "-mini")
    : "LLM";

  const config = {
    live: {
      icon: Zap,
      label: `${prettyModel} · LIVE`,
      sub: "real OpenAI request",
      bg: "bg-candy-mint-100/80 border-candy-mint-300/60",
      iconColor: "text-candy-mint-500",
    },
    mock: {
      icon: Cookie,
      label: "MOCK 模式",
      sub: "backend 已連線,但無 API key",
      bg: "bg-candy-lemon-100/80 border-candy-lemon-300/60",
      iconColor: "text-candy-lemon-500",
    },
    down: {
      icon: WifiOff,
      label: "Backend 未連線",
      sub: "請啟動 uvicorn",
      bg: "bg-candy-coral-100/80 border-candy-coral-300/60",
      iconColor: "text-candy-coral-500",
    },
    unknown: {
      icon: Wifi,
      label: "連線中…",
      sub: null,
      bg: "bg-candy-lavender-100/80 border-candy-lavender-300/60",
      iconColor: "text-candy-lavender-500",
    },
  }[backendStatus];

  const Icon = config.icon;

  if (compact) {
    return (
      <motion.span
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-display",
          config.bg,
        )}
        title={config.sub ?? ""}
      >
        <Icon className={cn("h-3 w-3", config.iconColor)} />
        {config.label}
      </motion.span>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1.5",
        config.bg,
      )}
    >
      <Icon className={cn("h-4 w-4", config.iconColor)} />
      <div className="flex flex-col leading-tight">
        <span className="font-display text-sm font-medium text-candy-cocoa">
          {config.label}
        </span>
        {config.sub && (
          <span className="text-xs text-candy-mocha">{config.sub}</span>
        )}
      </div>
    </motion.div>
  );
}
