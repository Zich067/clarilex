/**
 * Fetch wrappers for the FastAPI backend.
 * 預設指 localhost:8000；可由 NEXT_PUBLIC_API_BASE 覆蓋。
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type AnalysisMode = "baseline" | "rag" | "triangulation";

export interface RetrievalHit {
  chunk_id: string;
  score: number;
  text: string;
  metadata: {
    law_name?: string;
    article_no?: string;
    content?: string;
    court?: string;
    case_id?: string;
    cause?: string;
    section?: string;
  };
}

export interface IRACAnalysis {
  issue: string;
  rule: string;
  application: string;
  conclusion: string;
  risk_level: "low" | "medium" | "high";
  suggestions: string[];
  cited_articles: string[];
}

/** Flat hit dict returned by pipeline._hit_to_dict (chunk_id + score + metadata fields). */
export interface FlatHit {
  chunk_id: string;
  score: number;
  law_name?: string;
  article_no?: string;
  content?: string;
  court?: string;
  case_id?: string;
  cause?: string;
  section?: string;
  [key: string]: unknown;
}

export interface ClauseAnalysisDTO {
  clause_index: number;
  clause_label: string;
  clause_text: string;
  retrieved: FlatHit[];
  judgement_retrieved?: FlatHit[];
  cross_corroborated?: string[];
  analysis: IRACAnalysis | null;
  llm_source: string;
  duration_sec: number;
  audit?: {
    faithfulness: number;
    hallucination_rate: number;
    supported: number;
    partial: number;
    unsupported: number;
    advisory: number;
  };
}

export interface UploadResponse {
  doc_id: string;
  filename: string;
  page_count: number;
  text_chars: number;
  clause_count: number;
}

export interface JudgeReportDTO {
  citation: {
    cited: string[];
    grounded: string[];
    matched: string[];
    spurious: string[];
    missed: string[];
    precision: number;
    recall: number;
    f1: number;
  };
  audit: {
    claims: Array<{
      claim: string;
      status: "supported" | "partial" | "unsupported" | "advisory";
      anchor: string;
      rationale: string;
    }>;
    faithfulness: number;
    hallucination_rate: number;
    supported: number;
    partial: number;
    unsupported: number;
    advisory: number;
  };
  reasoning?: {
    rubric_score: number;
    semantic_cosine: number;
    combined: number;
  } | null;
  overall: number;
}

export interface RetrievalEvalDTO {
  generated_at: string;
  n_queries: number;
  laws_only: Record<
    string,
    {
      n: number;
      recall_at_k: number;
      precision_at_k: number;
      mrr: number;
      ndcg_at_k: number;
    }
  >;
  triangulator: {
    k: number;
    n: number;
    recall_at_k: number;
    precision_at_k: number;
    mrr: number;
    mean_judgement_hits: number;
    mean_cross_corroborated: number;
    queries_with_cross_match: number;
  };
}

export interface DevilsAdvocateDTO {
  rounds: Array<{
    round: number;
    topic: string;
    challenge: string;
    concession: string;
    score: number;
  }>;
  overall_robustness: number;
  recommendations: string[];
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json();
}

export const api = {
  /** Health / mock detection */
  health: () => json<{ status: string; mock: boolean; model: string }>("/api/health"),

  /** Quick demo: post inline text, get back doc_id (no PDF needed) */
  demo: (text: string, filename = "示範合約.txt") =>
    json<UploadResponse>("/api/demo", {
      method: "POST",
      body: JSON.stringify({ text, filename }),
    }),

  /** Upload a contract PDF; returns doc_id and clause count */
  async upload(file: File): Promise<UploadResponse> {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${API_BASE}/api/upload`, {
      method: "POST",
      body: fd,
    });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    return res.json();
  },

  clauses: (docId: string) =>
    json<{ clauses: { index: number; label: string; text: string }[] }>(
      `/api/docs/${docId}/clauses`,
    ),

  /** One-shot analyze (not streaming) — for demo where we want JSON back */
  analyze: (params: {
    doc_id: string;
    mode: AnalysisMode;
    audit?: boolean;
    max_clauses?: number;
  }) =>
    json<{ clauses: ClauseAnalysisDTO[] }>(`/api/analyze`, {
      method: "POST",
      body: JSON.stringify(params),
    }),

  /** Pure retrieval (no LLM) */
  retrieve: (q: string, collection: "laws" | "judgements" = "laws", k = 3) =>
    json<{ hits: RetrievalHit[] }>(
      `/api/retrieve?q=${encodeURIComponent(q)}&collection=${collection}&k=${k}`,
    ),

  judge: (analysis: IRACAnalysis, hits: Array<RetrievalHit | FlatHit>) =>
    json<JudgeReportDTO>(`/api/judge`, {
      method: "POST",
      body: JSON.stringify({ analysis, hits }),
    }),

  devilsAdvocate: (analysis: IRACAnalysis, hits: Array<RetrievalHit | FlatHit>) =>
    json<DevilsAdvocateDTO>(`/api/devils-advocate`, {
      method: "POST",
      body: JSON.stringify({ analysis, hits }),
    }),

  /** Pre-computed retrieval evaluation (from scripts/run_experiments.py) */
  retrievalEval: () => json<RetrievalEvalDTO>("/api/eval/retrieval"),

  /** Server-Sent Events for streaming clause-by-clause analysis */
  analyzeStream(
    params: { doc_id: string; mode: AnalysisMode; audit?: boolean },
    handlers: {
      onClause?: (c: ClauseAnalysisDTO) => void;
      onError?: (e: Error) => void;
      onDone?: () => void;
    },
  ) {
    const url = new URL(`${API_BASE}/api/analyze/stream`);
    url.searchParams.set("doc_id", params.doc_id);
    url.searchParams.set("mode", params.mode);
    if (params.audit) url.searchParams.set("audit", "1");

    const es = new EventSource(url.toString());
    es.addEventListener("clause", (e) => {
      try {
        handlers.onClause?.(JSON.parse((e as MessageEvent).data));
      } catch (err) {
        handlers.onError?.(err as Error);
      }
    });
    es.addEventListener("done", () => {
      handlers.onDone?.();
      es.close();
    });
    es.onerror = () => {
      handlers.onError?.(new Error("SSE connection error"));
      es.close();
    };
    return () => es.close();
  },
};
