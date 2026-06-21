"use client";

import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload,
  FileText,
  Sparkles,
  ArrowLeft,
  Play,
  Wand2,
  Gauge,
} from "lucide-react";
import { useDropzone } from "react-dropzone";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { CandyCard } from "@/components/candy/CandyCard";
import { GradientButton } from "@/components/candy/GradientButton";
import { RiskBadge } from "@/components/candy/RiskBadge";
import { CitationChip } from "@/components/candy/CitationChip";
import { SparkleSpinner } from "@/components/candy/SparkleSpinner";
import { BackendStatus } from "@/components/candy/BackendStatus";
import { ModeSwitch } from "@/components/analyze/ModeSwitch";
import { api, type ClauseAnalysisDTO } from "@/lib/api";
import { useAnalyzeStore } from "@/lib/store";
import { cn, type RiskLevel } from "@/lib/utils";
import { DEMO_CONTRACT_TEXT, DEMO_FILENAME } from "@/lib/demo-contract";

export default function AnalyzePage() {
  const {
    backendStatus,
    docId,
    filename,
    clauses,
    analyses,
    selectedClauseIndex,
    mode,
    auditEnabled,
    isAnalyzing,
    isUploading,
    streamProgress,
    setDoc,
    selectClause,
    pushAnalysis,
    setAnalyzing,
    setUploading,
    setAudit,
  } = useAnalyzeStore();

  const [stopFn, setStopFn] = useState<(() => void) | null>(null);

  const backendDown = backendStatus === "down";

  // ─── Upload PDF ───
  const onDrop = useCallback(
    async (files: File[]) => {
      const f = files[0];
      if (!f) return;
      if (backendDown) {
        toast.error("Backend 未啟動,請先 ./scripts/run_api.sh");
        return;
      }
      try {
        setUploading(true);
        toast(`上傳中 · ${f.name}`);
        const up = await api.upload(f);
        const list = await api.clauses(up.doc_id);
        setDoc(up.doc_id, up.filename, list.clauses);
        toast.success(`已切出 ${up.clause_count} 條條款`);
      } catch (e) {
        toast.error(`上傳失敗: ${(e as Error).message}`);
      } finally {
        setUploading(false);
      }
    },
    [backendDown, setDoc, setUploading],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    multiple: false,
    disabled: backendDown || isUploading || isAnalyzing,
  });

  // ─── Try demo contract ───
  const tryDemo = useCallback(async () => {
    if (backendDown) {
      toast.error("Backend 未啟動,請先 ./scripts/run_api.sh");
      return;
    }
    try {
      setUploading(true);
      const up = await api.demo(DEMO_CONTRACT_TEXT, DEMO_FILENAME);
      const list = await api.clauses(up.doc_id);
      setDoc(up.doc_id, up.filename, list.clauses);
      toast.success(`示範合約已載入 · ${up.clause_count} 條條款`);
    } catch (e) {
      toast.error(`載入失敗: ${(e as Error).message}`);
    } finally {
      setUploading(false);
    }
  }, [backendDown, setDoc, setUploading]);

  // Auto-load demo when first arriving with a healthy backend
  useEffect(() => {
    if (!docId && backendStatus === "live" && !isUploading) {
      // do not auto-load on live (might burn tokens). only auto-load in mock.
    }
    if (!docId && backendStatus === "mock" && !isUploading) {
      tryDemo();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendStatus]);

  // ─── Run analysis (SSE stream) ───
  const runAnalyze = useCallback(() => {
    if (!docId || backendDown) return;
    if (stopFn) stopFn();
    setAnalyzing(true);
    const stop = api.analyzeStream(
      { doc_id: docId, mode, audit: auditEnabled },
      {
        onClause: (c: ClauseAnalysisDTO) => {
          pushAnalysis(c);
          // 第一條來時自動選中
          if (selectedClauseIndex === null) selectClause(c.clause_index);
        },
        onDone: () => {
          setAnalyzing(false);
          toast.success("分析完成");
        },
        onError: (e) => {
          setAnalyzing(false);
          toast.error(`分析錯誤: ${e.message}`);
        },
      },
    );
    setStopFn(() => stop);
  }, [
    docId,
    backendDown,
    mode,
    auditEnabled,
    pushAnalysis,
    selectClause,
    selectedClauseIndex,
    stopFn,
    setAnalyzing,
  ]);

  // Cleanup on unmount
  useEffect(() => () => stopFn?.(), [stopFn]);

  // ─── Derived: currently selected analysis ───
  const currentAnalysis =
    selectedClauseIndex !== null ? analyses[selectedClauseIndex] : undefined;
  const currentClause =
    selectedClauseIndex !== null
      ? clauses.find((c) => c.index === selectedClauseIndex)
      : undefined;

  const riskOf = (idx: number): RiskLevel => {
    const a = analyses[idx];
    if (!a?.analysis) return "unknown";
    return (a.analysis.risk_level as RiskLevel) ?? "unknown";
  };

  // For citation chips: map article string → snippet for tooltip
  const articleSnippets = useMemo(() => {
    const map: Record<string, string> = {};
    if (!currentAnalysis) return map;
    for (const h of [
      ...currentAnalysis.retrieved,
      ...(currentAnalysis.judgement_retrieved ?? []),
    ]) {
      const key = `${h.law_name ?? ""}${h.article_no ?? ""}`.replace(/\s+/g, "");
      if (key && h.content) map[key] = h.content;
    }
    return map;
  }, [currentAnalysis]);

  return (
    <div className="flex min-h-screen flex-col">
      {/* Top nav */}
      <nav className="flex items-center justify-between gap-3 px-6 py-4 lg:px-10">
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
              明約 ClariLex
            </span>
            <span className="text-[10px] text-candy-mocha">合約條款分析</span>
          </div>
        </div>
        <BackendStatus />
      </nav>

      {/* Three-panel grid */}
      <div className="grid flex-1 grid-cols-1 gap-4 px-4 pb-8 lg:grid-cols-[300px_1fr_360px] lg:px-8">
        {/* ─────── Left: Upload + Mode + Clause list ─────── */}
        <aside className="flex flex-col gap-4">
          <CandyCard tint="pink" glow>
            <div
              {...getRootProps()}
              className={cn(
                "flex cursor-pointer flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-candy-pink-300 px-4 py-6 text-center transition-colors",
                isDragActive && "bg-candy-pink-100/60",
                (backendDown || isUploading || isAnalyzing) &&
                  "opacity-60 cursor-not-allowed",
              )}
            >
              <input {...getInputProps()} />
              <div className="candy-gradient flex h-12 w-12 items-center justify-center rounded-2xl">
                {isUploading ? (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ repeat: Infinity, duration: 1.4, ease: "linear" }}
                  >
                    <Sparkles className="h-5 w-5 text-white" />
                  </motion.div>
                ) : (
                  <Upload className="h-5 w-5 text-white" />
                )}
              </div>
              <div className="font-display text-sm font-medium text-candy-cocoa">
                {isUploading
                  ? "解析中…"
                  : isDragActive
                    ? "放開以上傳"
                    : "拖拉 PDF 或點擊上傳"}
              </div>
              <div className="text-xs text-candy-mocha">支援 JPG / PNG / PDF</div>
            </div>
            <button
              onClick={tryDemo}
              disabled={backendDown || isUploading || isAnalyzing}
              className="mt-3 w-full rounded-2xl border border-candy-pink-300/60 bg-white/70 px-3 py-2 text-sm font-display text-candy-cocoa transition-colors hover:bg-white disabled:opacity-50"
            >
              ✨ 載入示範合約
            </button>
          </CandyCard>

          <CandyCard tint="plain" glow className="space-y-3">
            <ModeSwitch />
            <label className="flex items-center justify-between gap-3 px-1">
              <span className="font-display text-xs text-candy-mocha">
                Claim Audit
              </span>
              <button
                onClick={() => setAudit(!auditEnabled)}
                className={cn(
                  "relative h-5 w-9 rounded-full transition-colors",
                  auditEnabled ? "bg-candy-lavender-500" : "bg-candy-pink-200",
                )}
              >
                <motion.span
                  className="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm"
                  animate={{ left: auditEnabled ? 18 : 2 }}
                  transition={{ type: "spring", stiffness: 300, damping: 24 }}
                />
              </button>
            </label>
            <GradientButton
              onClick={runAnalyze}
              disabled={!docId || backendDown || isAnalyzing}
              variant="candy"
              size="md"
              className="w-full"
            >
              {isAnalyzing ? (
                <>
                  <Sparkles className="h-4 w-4" />
                  分析中 {streamProgress.done}/{streamProgress.total}
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  開始分析 {clauses.length > 0 ? `(${clauses.length} 條)` : ""}
                </>
              )}
            </GradientButton>
          </CandyCard>

          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between px-2">
              <span className="font-display text-sm font-medium text-candy-cocoa">
                條款列表
              </span>
              <span className="text-xs text-candy-mocha">
                {clauses.length} 條 · 已分析 {Object.keys(analyses).length}
              </span>
            </div>
            {clauses.length === 0 && (
              <CandyCard tint="lavender" className="text-center text-sm text-candy-mocha">
                {backendDown
                  ? "Backend 未連線 — 啟動後將自動載入示範合約。"
                  : "點上方「載入示範合約」或拖拉合約 PDF。"}
              </CandyCard>
            )}
            {clauses.map((c) => {
              const risk = riskOf(c.index);
              const done = !!analyses[c.index];
              return (
                <motion.button
                  key={c.index}
                  whileHover={{ x: 2 }}
                  onClick={() => selectClause(c.index)}
                  className={cn(
                    "flex flex-col gap-2 rounded-2xl border p-3 text-left transition-all",
                    selectedClauseIndex === c.index
                      ? "border-candy-pink-300 bg-white/90 shadow-[0_8px_24px_rgba(255,182,217,0.25)]"
                      : "border-transparent bg-white/40 hover:bg-white/60",
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-display text-sm font-medium text-candy-cocoa">
                      {c.label}
                    </span>
                    {done ? (
                      <RiskBadge level={risk} size="sm" showLabel={false} />
                    ) : (
                      <span className="text-[10px] text-candy-mocha">待分析</span>
                    )}
                  </div>
                  <p className="line-clamp-2 text-xs leading-relaxed text-candy-mocha">
                    {c.text}
                  </p>
                </motion.button>
              );
            })}
          </div>
        </aside>

        {/* ─────── Center: IRAC Report ─────── */}
        <main className="flex flex-col gap-4">
          {(docId || filename) && (
            <CandyCard tint="lavender" glow className="flex items-center gap-3">
              <FileText className="h-5 w-5 text-candy-lavender-500" />
              <div className="flex-1">
                <div className="font-display text-sm font-medium text-candy-cocoa">
                  {filename}
                </div>
                <div className="text-xs text-candy-mocha">
                  doc_id: <span className="font-mono">{docId}</span> · {clauses.length}{" "}
                  條條款 · 模式: <span className="font-mono uppercase">{mode}</span>
                </div>
              </div>
              {isAnalyzing && <SparkleSpinner />}
            </CandyCard>
          )}

          <AnimatePresence mode="wait">
            {currentAnalysis ? (
              <motion.div
                key={`a-${currentAnalysis.clause_index}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
              >
                <IRACReport
                  clauseLabel={currentClause?.label ?? "—"}
                  clauseText={currentClause?.text ?? ""}
                  data={currentAnalysis}
                  snippets={articleSnippets}
                />
              </motion.div>
            ) : currentClause ? (
              <CandyCard tint="plain" glow className="space-y-3 text-center">
                <Wand2 className="mx-auto h-8 w-8 text-candy-lavender-500" />
                <h2 className="font-display text-xl font-bold text-candy-cocoa">
                  {currentClause.label}
                </h2>
                <blockquote className="rounded-2xl border border-candy-pink-200/60 bg-white/70 p-4 text-left text-sm leading-relaxed text-candy-mocha">
                  {currentClause.text}
                </blockquote>
                <p className="text-sm text-candy-mocha">
                  點左側「開始分析」啟動 RAG pipeline。
                </p>
              </CandyCard>
            ) : (
              <CandyCard tint="plain" glow className="text-center">
                <Sparkles className="mx-auto h-8 w-8 text-candy-lavender-500" />
                <p className="mt-3 font-display text-candy-cocoa">
                  先載入合約,選一條條款即可看到 IRAC 風險報告。
                </p>
              </CandyCard>
            )}
          </AnimatePresence>

          {currentAnalysis && (
            <div className="flex items-center justify-between rounded-3xl glass p-5">
              <div>
                <div className="font-display text-sm font-medium text-candy-cocoa">
                  跑 LLM-as-Judge?
                </div>
                <div className="text-xs text-candy-mocha">
                  量化 Faithfulness、Citation F1、Reasoning Similarity
                </div>
              </div>
              <Link href={`/eval?clause=${currentAnalysis.clause_index}`}>
                <GradientButton variant="cool" size="sm">
                  <Gauge className="h-4 w-4" />
                  看評估儀表板
                </GradientButton>
              </Link>
            </div>
          )}
        </main>

        {/* ─────── Right: Evidence panel ─────── */}
        <aside className="flex flex-col gap-4">
          <EvidencePanel data={currentAnalysis} />
        </aside>
      </div>
    </div>
  );
}

/* ────────────────────────── Sub-components ────────────────────────── */

function IRACReport({
  clauseLabel,
  clauseText,
  data,
  snippets,
}: {
  clauseLabel: string;
  clauseText: string;
  data: ClauseAnalysisDTO;
  snippets: Record<string, string>;
}) {
  const a = data.analysis;
  if (!a) {
    return (
      <CandyCard tint="coral" glow>
        <p className="text-sm text-candy-cocoa">分析失敗或回傳格式錯誤。</p>
      </CandyCard>
    );
  }
  const risk = (a.risk_level as RiskLevel) ?? "unknown";

  return (
    <CandyCard tint="plain" glow className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col">
          <span className="text-sm text-candy-mocha">{clauseLabel}</span>
          <h2 className="mt-1 font-display text-2xl font-bold text-candy-cocoa">
            IRAC 風險分析
          </h2>
          <span className="mt-1 text-xs text-candy-mocha">
            來源: <span className="font-mono uppercase">{data.llm_source}</span> ·{" "}
            {data.duration_sec}s
          </span>
        </div>
        <RiskBadge level={risk} size="lg" />
      </div>

      <blockquote className="rounded-2xl border border-candy-pink-200/60 bg-white/70 p-4 text-sm leading-relaxed text-candy-mocha">
        {clauseText}
      </blockquote>

      <Section title="爭點（Issue）" tint="pink">
        {a.issue}
      </Section>

      <Section title="法律規定（Rule）" tint="lavender">
        <div className="space-y-2">
          <div>{a.rule}</div>
          {a.cited_articles && a.cited_articles.length > 0 && (
            <div className="flex flex-wrap gap-2 pt-1">
              {a.cited_articles.map((art) => {
                const key = art.replace(/\s+/g, "");
                return (
                  <CitationChip
                    key={art}
                    article={art}
                    detail={snippets[key]}
                  />
                );
              })}
            </div>
          )}
        </div>
      </Section>

      <Section title="涵攝（Application）" tint="sky">
        {a.application}
      </Section>

      <Section title="結論（Conclusion）" tint="coral">
        <div className="space-y-3">
          <div>{a.conclusion}</div>
          {a.suggestions && a.suggestions.length > 0 && (
            <ul className="space-y-1.5">
              {a.suggestions.map((s) => (
                <li
                  key={s}
                  className="flex items-start gap-2 rounded-2xl bg-candy-mint-100/60 px-3 py-2 text-sm text-candy-cocoa"
                >
                  <Sparkles className="mt-0.5 h-4 w-4 text-candy-mint-500" />
                  {s}
                </li>
              ))}
            </ul>
          )}
        </div>
      </Section>

      {data.audit && (
        <Section title="Claim-Faithfulness 稽核" tint="lavender">
          <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <ClaimStatPill label="supported" value={data.audit.supported} tint="mint" />
            <ClaimStatPill label="partial" value={data.audit.partial} tint="lemon" />
            <ClaimStatPill
              label="unsupported"
              value={data.audit.unsupported}
              tint="coral"
            />
            <ClaimStatPill
              label="advisory"
              value={data.audit.advisory}
              tint="lavender"
            />
          </div>
          <div className="mt-3 text-xs text-candy-mocha">
            Faithfulness {(data.audit.faithfulness * 100).toFixed(0)}% · Hallucination{" "}
            {(data.audit.hallucination_rate * 100).toFixed(0)}%
          </div>
        </Section>
      )}
    </CandyCard>
  );
}

function EvidencePanel({ data }: { data?: ClauseAnalysisDTO }) {
  if (!data) {
    return (
      <CandyCard tint="plain" glow>
        <span className="font-display text-sm font-medium text-candy-cocoa">
          檢索證據
        </span>
        <p className="mt-2 text-xs text-candy-mocha">
          選一條條款後將顯示對應的法規 / 判決命中。
        </p>
      </CandyCard>
    );
  }

  const laws = data.retrieved ?? [];
  const judgements = data.judgement_retrieved ?? [];
  const cross = data.cross_corroborated ?? [];

  return (
    <>
      <CandyCard tint="plain" glow>
        <div className="flex items-center justify-between">
          <span className="font-display text-sm font-medium text-candy-cocoa">
            檢索證據
          </span>
          <span className="text-xs text-candy-mocha">
            Laws {laws.length} · Judg. {judgements.length}
          </span>
        </div>
      </CandyCard>

      {laws.map((h, i) => (
        <CandyCard key={`L${i}`} tint="lavender" glow className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-candy-cocoa">
              [L{i + 1}] {h.law_name ?? ""} {h.article_no ?? ""}
            </span>
            <span className="rounded-full bg-white/70 px-2 py-0.5 text-xs font-mono text-candy-mocha">
              {h.score?.toFixed(2)}
            </span>
          </div>
          <p className="line-clamp-5 text-xs leading-relaxed text-candy-mocha">
            {h.content}
          </p>
        </CandyCard>
      ))}

      {judgements.map((h, i) => (
        <CandyCard key={`J${i}`} tint="sky" glow className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-candy-cocoa">
              [J{i + 1}] {h.court ?? ""} {h.case_id ?? ""}
            </span>
            <span className="rounded-full bg-white/70 px-2 py-0.5 text-xs font-mono text-candy-mocha">
              {h.score?.toFixed(2)}
            </span>
          </div>
          <p className="line-clamp-4 text-xs leading-relaxed text-candy-mocha">
            {h.content}
          </p>
        </CandyCard>
      ))}

      {cross.length > 0 && (
        <CandyCard tint="mint" glow>
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-candy-mint-500" />
            <span className="font-display text-sm font-medium text-candy-cocoa">
              跨索引佐證
            </span>
          </div>
          <p className="mt-1 text-xs text-candy-mocha">
            下列條號同時被法規索引與判決理由命中,信度提升：
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {cross.map((c) => (
              <span
                key={c}
                className="rounded-full bg-white/70 px-2.5 py-0.5 font-mono text-xs text-candy-mint-500"
              >
                {c}
              </span>
            ))}
          </div>
        </CandyCard>
      )}

      {laws.length === 0 && judgements.length === 0 && (
        <CandyCard tint="lemon" glow>
          <p className="text-xs text-candy-mocha">
            無檢索命中 — 此 clause 可能在 baseline 模式（純 LLM）。
          </p>
        </CandyCard>
      )}
    </>
  );
}

function Section({
  title,
  tint,
  children,
}: {
  title: string;
  tint: "pink" | "lavender" | "sky" | "coral";
  children: React.ReactNode;
}) {
  const tintMap = {
    pink: "bg-candy-pink-100/60 border-candy-pink-200/60",
    lavender: "bg-candy-lavender-100/60 border-candy-lavender-300/40",
    sky: "bg-candy-sky-100/60 border-candy-sky-300/40",
    coral: "bg-candy-coral-100/60 border-candy-coral-300/40",
  };
  return (
    <div className={cn("rounded-2xl border p-4", tintMap[tint])}>
      <div className="mb-2 font-display text-sm font-semibold text-candy-cocoa">
        {title}
      </div>
      <div className="text-sm leading-relaxed text-candy-mocha">{children}</div>
    </div>
  );
}

function ClaimStatPill({
  label,
  value,
  tint,
}: {
  label: string;
  value: number;
  tint: "mint" | "lemon" | "coral" | "lavender";
}) {
  const tintMap = {
    mint: "bg-candy-mint-100/80",
    lemon: "bg-candy-lemon-100/80",
    coral: "bg-candy-coral-100/80",
    lavender: "bg-candy-lavender-100/80",
  };
  return (
    <div className={cn("rounded-2xl p-2 text-center", tintMap[tint])}>
      <div className="font-display text-lg font-bold text-candy-cocoa">{value}</div>
      <div className="font-mono text-[10px] text-candy-mocha">{label}</div>
    </div>
  );
}
