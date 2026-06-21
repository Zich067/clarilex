"use client";

import Link from "next/link";
import {
  ArrowLeft,
  Sparkles,
  Swords,
  Search,
  CheckCircle2,
  RefreshCw,
} from "lucide-react";
import { CandyCard } from "@/components/candy/CandyCard";
import { GradientButton } from "@/components/candy/GradientButton";
import { ScoreGauge } from "@/components/candy/ScoreGauge";
import { BackendStatus } from "@/components/candy/BackendStatus";
import { SparkleSpinner } from "@/components/candy/SparkleSpinner";
import { motion } from "framer-motion";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAnalyzeStore, selectCurrentAnalysis } from "@/lib/store";
import {
  api,
  type FlatHit,
  type IRACAnalysis,
  type JudgeReportDTO,
  type DevilsAdvocateDTO,
  type RetrievalEvalDTO,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

/**
 * /eval — 評估儀表板
 *
 * 三軌:
 *  1. LLM-as-Judge (真實 /api/judge) - 從目前選中的 clause analysis 拿來打分
 *  2. Devil's Advocate (真實 /api/devils-advocate) - 三輪挑戰
 *  3. Baseline vs RAG vs Triangulation 對照表 - 目前以 mock 數據展示 (留待 §6 跑實驗後補)
 */

const MOCK_COMPARISON = [
  {
    name: "Baseline（純 LLM）",
    tint: "coral" as const,
    faithfulness: 0.46,
    citation_f1: 0.31,
    hallucination: 0.62,
    note: "幻覺率高,多次引用不存在之條號",
  },
  {
    name: "RAG（單軌）",
    tint: "lemon" as const,
    faithfulness: 0.79,
    citation_f1: 0.84,
    hallucination: 0.13,
    note: "顯著降低幻覺,仍偶有 spurious citation",
  },
  {
    name: "RAG + Triangulation",
    tint: "mint" as const,
    faithfulness: 0.88,
    citation_f1: 0.92,
    hallucination: 0.08,
    note: "跨索引佐證進一步提升精準度",
  },
];


export default function EvalPage() {
  const backendDown = useAnalyzeStore((s) => s.backendStatus === "down");
  const current = useAnalyzeStore(selectCurrentAnalysis);
  const clauses = useAnalyzeStore((s) => s.clauses);

  const analysis: IRACAnalysis | undefined = current?.analysis ?? undefined;
  const hits: FlatHit[] = useMemo(() => {
    if (!current) return [];
    return [...(current.retrieved ?? []), ...(current.judgement_retrieved ?? [])];
  }, [current]);

  const canEval = !!analysis && !backendDown;
  const [bump, setBump] = useState(0);

  const judgeQuery = useQuery<JudgeReportDTO>({
    queryKey: ["judge", current?.clause_index, bump],
    queryFn: () => api.judge(analysis!, hits),
    enabled: canEval,
    retry: false,
  });

  const devilQuery = useQuery<DevilsAdvocateDTO>({
    queryKey: ["devil", current?.clause_index, bump],
    queryFn: () => api.devilsAdvocate(analysis!, hits),
    enabled: canEval,
    retry: false,
  });

  const retrievalQuery = useQuery<RetrievalEvalDTO>({
    queryKey: ["retrieval-eval"],
    queryFn: api.retrievalEval,
    retry: false,
    refetchOnWindowFocus: false,
  });

  return (
    <div className="flex min-h-screen flex-col gap-6 px-6 py-8 lg:px-12">
      {/* Top nav */}
      <nav className="flex items-center justify-between gap-3">
        <Link
          href="/"
          className="flex items-center gap-2 text-sm text-candy-mocha hover:text-candy-cocoa"
        >
          <ArrowLeft className="h-4 w-4" />
          回首頁
        </Link>
        <div className="flex items-center gap-3">
          <div className="candy-gradient flex h-9 w-9 items-center justify-center rounded-xl">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="font-display text-base font-bold text-candy-cocoa">
              評估儀表板
            </span>
            <span className="text-[10px] text-candy-mocha">
              Judge · Devil&apos;s Advocate · Retrieval
            </span>
          </div>
        </div>
        <BackendStatus />
      </nav>

      <header className="flex flex-col gap-2">
        <h1 className="font-display text-3xl font-bold text-candy-cocoa lg:text-4xl">
          LLM-as-Judge · Devil&apos;s Advocate · 系統對照
        </h1>
        <p className="text-candy-mocha">
          {current
            ? `對目前選中的 ${current.clause_label}（${clauses.find((c) => c.index === current.clause_index)?.label ?? ""}）即時跑評估。`
            : backendDown
              ? "Backend 未連線 — 請先啟動 uvicorn,並到 /analyze 跑分析。"
              : "尚未選擇任何條款。請到 /analyze 頁面跑分析,再回來看評估。"}
        </p>
        {!current && (
          <Link href="/analyze">
            <GradientButton variant="candy" size="sm">
              <Sparkles className="h-4 w-4" />
              去 /analyze 跑分析
            </GradientButton>
          </Link>
        )}
      </header>

      {/* ─── LLM-as-Judge ─── */}
      <CandyCard tint="plain" glow className="space-y-5">
        <div className="flex items-center gap-3">
          <CheckCircle2 className="h-5 w-5 text-candy-lavender-500" />
          <h2 className="font-display text-xl font-semibold text-candy-cocoa">
            LLM-as-Judge 三軌評分
          </h2>
          {judgeQuery.data && (
            <span className="ml-auto rounded-full bg-candy-lavender-100 px-3 py-1 font-display text-sm text-candy-lavender-500">
              Overall {judgeQuery.data.overall.toFixed(2)}
            </span>
          )}
          {canEval && (
            <button
              onClick={() => {
                setBump((b) => b + 1);
                toast("重新跑 judge…");
              }}
              className="rounded-full bg-white/70 p-1.5 hover:bg-white"
              title="重新評估"
            >
              <RefreshCw className="h-3.5 w-3.5 text-candy-mocha" />
            </button>
          )}
        </div>

        {judgeQuery.isFetching && (
          <SparkleSpinner label="跑 LLM-as-Judge 中..." />
        )}

        {judgeQuery.isError && (
          <CandyCard tint="coral">
            <p className="text-sm text-candy-coral-500">
              Judge 呼叫失敗: {(judgeQuery.error as Error).message}
            </p>
          </CandyCard>
        )}

        {judgeQuery.data && (
          <>
            <div className="grid grid-cols-2 gap-6 lg:grid-cols-4">
              <ScoreGauge
                value={judgeQuery.data.audit.faithfulness}
                label="Faithfulness"
                tint="mint"
              />
              <ScoreGauge
                value={judgeQuery.data.citation.f1}
                label="Citation F1"
                tint="lavender"
              />
              <ScoreGauge
                value={judgeQuery.data.reasoning?.combined ?? 0}
                label="Reasoning Sim."
                tint="sky"
              />
              <ScoreGauge
                value={judgeQuery.data.overall}
                label="Overall"
                tint="pink"
              />
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Pill
                tint="mint"
                label="引用命中"
                value={judgeQuery.data.citation.matched.length}
                sub={judgeQuery.data.citation.matched.join("、") || "—"}
              />
              <Pill
                tint="coral"
                label="幻覺引用"
                value={judgeQuery.data.citation.spurious.length}
                sub={judgeQuery.data.citation.spurious.join("、") || "零幻覺 🎉"}
              />
              <Pill
                tint="lemon"
                label="缺漏引用"
                value={judgeQuery.data.citation.missed.length}
                sub={judgeQuery.data.citation.missed.join("、") || "—"}
              />
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <ClaimStat
                tint="mint"
                label="supported"
                value={judgeQuery.data.audit.supported}
              />
              <ClaimStat
                tint="lemon"
                label="partial"
                value={judgeQuery.data.audit.partial}
              />
              <ClaimStat
                tint="coral"
                label="unsupported"
                value={judgeQuery.data.audit.unsupported}
              />
              <ClaimStat
                tint="lavender"
                label="advisory"
                value={judgeQuery.data.audit.advisory}
              />
            </div>

            {judgeQuery.data.audit.claims.length > 0 && (
              <div className="space-y-2">
                <div className="font-display text-sm font-semibold text-candy-cocoa">
                  逐主張稽核
                </div>
                {judgeQuery.data.audit.claims.map((c, i) => (
                  <div
                    key={i}
                    className={cn(
                      "rounded-2xl border p-3 text-sm",
                      c.status === "supported" &&
                        "border-candy-mint-300/40 bg-candy-mint-100/40",
                      c.status === "partial" &&
                        "border-candy-lemon-300/40 bg-candy-lemon-100/40",
                      c.status === "unsupported" &&
                        "border-candy-coral-300/40 bg-candy-coral-100/40",
                      c.status === "advisory" &&
                        "border-candy-lavender-300/40 bg-candy-lavender-100/40",
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="rounded-full bg-white/80 px-2 py-0.5 font-mono text-xs text-candy-cocoa">
                        {c.status}
                      </span>
                      {c.anchor && (
                        <span className="font-mono text-xs text-candy-mocha">
                          {c.anchor}
                        </span>
                      )}
                    </div>
                    <p className="mt-1.5 text-sm text-candy-cocoa">{c.claim}</p>
                    {c.rationale && (
                      <p className="mt-1 text-xs text-candy-mocha">
                        {c.rationale}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {!canEval && (
          <p className="text-sm text-candy-mocha">
            目前無 analysis 可評估。請先到 /analyze 跑分析。
          </p>
        )}
      </CandyCard>

      {/* ─── Devil's Advocate ─── */}
      <CandyCard tint="plain" glow className="space-y-4">
        <div className="flex items-center gap-3">
          <Swords className="h-5 w-5 text-candy-coral-500" />
          <h2 className="font-display text-xl font-semibold text-candy-cocoa">
            Devil&apos;s Advocate 三輪挑戰
          </h2>
          {devilQuery.data && (
            <span className="ml-auto rounded-full bg-candy-mint-100 px-3 py-1 font-display text-sm text-candy-mint-500">
              Robustness {(devilQuery.data.overall_robustness * 100).toFixed(0)}%
            </span>
          )}
        </div>

        {devilQuery.isFetching && (
          <SparkleSpinner label="魔鬼代言人正在找碴..." />
        )}

        {devilQuery.isError && (
          <CandyCard tint="coral">
            <p className="text-sm text-candy-coral-500">
              Devil&apos;s Advocate 呼叫失敗: {(devilQuery.error as Error).message}
            </p>
          </CandyCard>
        )}

        {devilQuery.data && (
          <>
            <div className="grid gap-4 md:grid-cols-3">
              {devilQuery.data.rounds.map((r, i) => (
                <motion.div
                  key={r.round}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className="space-y-2 rounded-2xl border border-candy-coral-300/40 bg-candy-coral-100/50 p-4"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="min-w-0 font-display text-sm font-semibold text-candy-cocoa">
                      Round {r.round} · {r.topic}
                    </span>
                    <span className="shrink-0 whitespace-nowrap rounded-full bg-white/80 px-2.5 py-0.5 font-mono text-xs">
                      {r.score.toFixed(1)} / 5
                    </span>
                  </div>
                  <div>
                    <div className="font-display text-xs text-candy-coral-500">
                      挑戰
                    </div>
                    <p className="text-sm text-candy-mocha">{r.challenge}</p>
                  </div>
                  {r.concession && (
                    <div>
                      <div className="font-display text-xs text-candy-mint-500">
                        讓步
                      </div>
                      <p className="text-sm text-candy-mocha">{r.concession}</p>
                    </div>
                  )}
                </motion.div>
              ))}
            </div>
            {devilQuery.data.recommendations.length > 0 && (
              <div className="rounded-2xl border border-candy-mint-300/40 bg-candy-mint-100/50 p-4">
                <div className="mb-2 font-display text-sm font-semibold text-candy-cocoa">
                  修正建議
                </div>
                <ul className="space-y-1.5">
                  {devilQuery.data.recommendations.map((rec) => (
                    <li
                      key={rec}
                      className="flex items-start gap-2 text-sm text-candy-mocha"
                    >
                      <Sparkles className="mt-0.5 h-4 w-4 text-candy-mint-500" />
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </CandyCard>

      {/* ─── Mock Comparison ─── */}
      <CandyCard tint="plain" glow className="space-y-4">
        <div className="flex items-center gap-3">
          <Search className="h-5 w-5 text-candy-sky-500" />
          <h2 className="font-display text-xl font-semibold text-candy-cocoa">
            Baseline · RAG · Triangulation 對照
          </h2>
          <span className="ml-auto rounded-full bg-candy-lemon-100 px-2.5 py-0.5 text-xs font-display text-candy-lemon-500">
            示意數據（待 §6 實驗補實）
          </span>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {MOCK_COMPARISON.map((c) => (
            <CandyCard key={c.name} tint={c.tint} glow className="space-y-3">
              <div className="font-display text-base font-semibold text-candy-cocoa">
                {c.name}
              </div>
              <Row label="Faithfulness" value={c.faithfulness} />
              <Row label="Citation F1" value={c.citation_f1} />
              <Row label="Hallucination" value={c.hallucination} invert />
              <p className="text-xs text-candy-mocha">{c.note}</p>
            </CandyCard>
          ))}
        </div>
      </CandyCard>

      {/* ─── Retrieval metrics (real) ─── */}
      <CandyCard tint="plain" glow className="space-y-4">
        <div className="flex items-center gap-3">
          <Search className="h-5 w-5 text-candy-lavender-500" />
          <h2 className="font-display text-xl font-semibold text-candy-cocoa">
            檢索準確度（Gold Standard 實測）
          </h2>
          {retrievalQuery.data ? (
            <span className="ml-auto rounded-full bg-candy-mint-100 px-2.5 py-0.5 text-xs font-display text-candy-mint-500">
              真實實驗 · n={retrievalQuery.data.n_queries} · {retrievalQuery.data.generated_at}
            </span>
          ) : retrievalQuery.isFetching ? (
            <span className="ml-auto text-xs text-candy-mocha">載入中…</span>
          ) : (
            <span className="ml-auto rounded-full bg-candy-coral-100 px-2.5 py-0.5 text-xs font-display text-candy-coral-500">
              尚未跑實驗
            </span>
          )}
        </div>

        {retrievalQuery.isError && (
          <CandyCard tint="lemon">
            <p className="text-sm text-candy-mocha">
              {(retrievalQuery.error as Error).message}
            </p>
            <p className="mt-1 text-xs text-candy-mocha">
              請執行: <code className="font-mono">python scripts/run_experiments.py</code>
            </p>
          </CandyCard>
        )}

        {retrievalQuery.data && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-candy-mocha">
                    <th className="px-3 py-2 font-display">K</th>
                    <th className="px-3 py-2 font-display">Recall@K</th>
                    <th className="px-3 py-2 font-display">Precision@K</th>
                    <th className="px-3 py-2 font-display">MRR</th>
                    <th className="px-3 py-2 font-display">nDCG@K</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(retrievalQuery.data.laws_only)
                    .sort(([a], [b]) => parseInt(a) - parseInt(b))
                    .map(([k, s]) => (
                      <tr
                        key={k}
                        className="rounded-2xl bg-white/60 text-candy-cocoa"
                      >
                        <td className="px-3 py-2 font-display">{k}</td>
                        <td className="px-3 py-2 font-mono">
                          {s.recall_at_k.toFixed(3)}
                        </td>
                        <td className="px-3 py-2 font-mono">
                          {s.precision_at_k.toFixed(3)}
                        </td>
                        <td className="px-3 py-2 font-mono">
                          {s.mrr.toFixed(3)}
                        </td>
                        <td className="px-3 py-2 font-mono">
                          {s.ndcg_at_k.toFixed(3)}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Pill
                tint="lemon"
                label="Triangulator k"
                value={retrievalQuery.data.triangulator.k}
                sub={`Recall@k = ${retrievalQuery.data.triangulator.recall_at_k.toFixed(3)}`}
              />
              <Pill
                tint="mint"
                label="平均跨索引佐證"
                value={Number(
                  retrievalQuery.data.triangulator.mean_cross_corroborated.toFixed(2),
                )}
                sub={`含跨索引命中 gold 條號的 query: ${retrievalQuery.data.triangulator.queries_with_cross_match}/${retrievalQuery.data.triangulator.n}`}
              />
              <Pill
                tint="coral"
                label="平均判決命中"
                value={Number(
                  retrievalQuery.data.triangulator.mean_judgement_hits.toFixed(2),
                )}
                sub="每 query 命中的判決 chunk 數"
              />
            </div>
          </>
        )}
      </CandyCard>
    </div>
  );
}

/* ─────────────── helpers ─────────────── */

function Pill({
  tint,
  label,
  value,
  sub,
}: {
  tint: "mint" | "coral" | "lemon";
  label: string;
  value: number;
  sub: string;
}) {
  const tintMap = {
    mint: "bg-candy-mint-100/70 border-candy-mint-300/40",
    coral: "bg-candy-coral-100/70 border-candy-coral-300/40",
    lemon: "bg-candy-lemon-100/70 border-candy-lemon-300/40",
  };
  return (
    <div className={cn("rounded-2xl border p-3", tintMap[tint])}>
      <div className="flex items-center justify-between">
        <span className="font-display text-sm font-medium text-candy-cocoa">
          {label}
        </span>
        <span className="font-display text-xl font-bold text-candy-cocoa">
          {value}
        </span>
      </div>
      <p className="mt-1 line-clamp-2 text-xs text-candy-mocha">{sub}</p>
    </div>
  );
}

function ClaimStat({
  tint,
  label,
  value,
}: {
  tint: "mint" | "lemon" | "coral" | "lavender";
  label: string;
  value: number;
}) {
  const tintMap = {
    mint: "bg-candy-mint-100/70",
    lemon: "bg-candy-lemon-100/70",
    coral: "bg-candy-coral-100/70",
    lavender: "bg-candy-lavender-100/70",
  };
  return (
    <div className={cn("rounded-2xl p-3 text-center", tintMap[tint])}>
      <div className="font-display text-xl font-bold text-candy-cocoa">{value}</div>
      <div className="font-mono text-xs text-candy-mocha">{label}</div>
    </div>
  );
}

function Row({
  label,
  value,
  invert = false,
}: {
  label: string;
  value: number;
  invert?: boolean;
}) {
  const goodness = invert ? 1 - value : value;
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-candy-mocha">
        <span>{label}</span>
        <span className="font-mono">{value.toFixed(2)}</span>
      </div>
      <div className="h-2 rounded-full bg-white/60">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${Math.max(4, goodness * 100)}%` }}
          transition={{ duration: 0.8 }}
          className={cn(
            "h-full rounded-full",
            invert ? "candy-gradient-warm" : "candy-gradient-fresh",
          )}
        />
      </div>
    </div>
  );
}
