import { create } from "zustand";
import type {
  AnalysisMode,
  ClauseAnalysisDTO,
  RetrievalHit,
} from "./api";

export interface ClauseSummary {
  index: number;
  label: string;
  text: string;
}

interface AnalyzeState {
  apiBase: string;
  backendStatus: "unknown" | "live" | "mock" | "down";
  modelName: string | null;

  docId: string | null;
  filename: string | null;
  clauses: ClauseSummary[];
  analyses: Record<number, ClauseAnalysisDTO>;
  selectedClauseIndex: number | null;
  mode: AnalysisMode;
  auditEnabled: boolean;
  isAnalyzing: boolean;
  isUploading: boolean;
  streamProgress: { done: number; total: number };

  setBackendStatus: (s: AnalyzeState["backendStatus"], model?: string | null) => void;
  setDoc: (docId: string, filename: string, clauses: ClauseSummary[]) => void;
  setMode: (mode: AnalysisMode) => void;
  setAudit: (enabled: boolean) => void;
  selectClause: (index: number | null) => void;
  pushAnalysis: (c: ClauseAnalysisDTO) => void;
  setAnalyzing: (b: boolean) => void;
  setUploading: (b: boolean) => void;
  setStreamProgress: (p: { done: number; total: number }) => void;
  reset: () => void;
}

export const useAnalyzeStore = create<AnalyzeState>((set) => ({
  apiBase: process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000",
  backendStatus: "unknown",
  modelName: null,

  docId: null,
  filename: null,
  clauses: [],
  analyses: {},
  selectedClauseIndex: null,
  mode: "triangulation",
  auditEnabled: true,
  isAnalyzing: false,
  isUploading: false,
  streamProgress: { done: 0, total: 0 },

  setBackendStatus: (backendStatus, modelName = null) =>
    set({ backendStatus, modelName: modelName ?? null }),
  setDoc: (docId, filename, clauses) =>
    set({
      docId,
      filename,
      clauses,
      analyses: {},
      selectedClauseIndex: clauses[0]?.index ?? null,
      streamProgress: { done: 0, total: clauses.length },
    }),
  setMode: (mode) => set({ mode }),
  setAudit: (auditEnabled) => set({ auditEnabled }),
  selectClause: (index) => set({ selectedClauseIndex: index }),
  pushAnalysis: (c) =>
    set((s) => ({
      analyses: { ...s.analyses, [c.clause_index]: c },
      streamProgress: {
        done: Object.keys({ ...s.analyses, [c.clause_index]: c }).length,
        total: s.clauses.length,
      },
    })),
  setAnalyzing: (isAnalyzing) => set({ isAnalyzing }),
  setUploading: (isUploading) => set({ isUploading }),
  setStreamProgress: (streamProgress) => set({ streamProgress }),
  reset: () =>
    set({
      docId: null,
      filename: null,
      clauses: [],
      analyses: {},
      selectedClauseIndex: null,
      isAnalyzing: false,
      isUploading: false,
      streamProgress: { done: 0, total: 0 },
    }),
}));

/** Helper to get the currently selected analysis (or undefined if not yet ready). */
export const selectCurrentAnalysis = (s: AnalyzeState) =>
  s.selectedClauseIndex !== null ? s.analyses[s.selectedClauseIndex] : undefined;
