import Link from "next/link";
import {
  ScrollText,
  Sparkles,
  Scale,
  ShieldCheck,
  Brain,
  Gauge,
} from "lucide-react";
import { CandyCard } from "@/components/candy/CandyCard";
import { GradientButton } from "@/components/candy/GradientButton";

const features = [
  {
    icon: ScrollText,
    title: "OCR 自動轉文字",
    desc: "拖拉上傳租賃／買賣合約(支援 JPG / PNG / PDF),pdfplumber + Tesseract OCR 雙軌解析。",
    tint: "pink" as const,
  },
  {
    icon: Brain,
    title: "向量檢索 + RAG",
    desc: "Arctic 1024 維嵌入 + ChromaDB Cosine，把民法／民訴／消保法 + 近一年司法院判決即時拉到 LLM 面前。",
    tint: "lavender" as const,
  },
  {
    icon: Scale,
    title: "IRAC 結構化分析",
    desc: "資深律師 persona + Chain-of-Thought，逐條輸出 Issue / Rule / Application / Conclusion。",
    tint: "sky" as const,
  },
  {
    icon: ShieldCheck,
    title: "三角驗證",
    desc: "同條號同時被法規與判決命中時提高信度，過濾單軌幻覺。",
    tint: "mint" as const,
  },
  {
    icon: Gauge,
    title: "LLM-as-Judge",
    desc: "Faithfulness / Citation F1 / Reasoning Similarity 三軌量化，並標出每個主張的出處。",
    tint: "lemon" as const,
  },
  {
    icon: Sparkles,
    title: "Devil's Advocate",
    desc: "三輪魔鬼代言人挑戰，預設找碴，需 ≥ 4/5 強證據才讓步。",
    tint: "coral" as const,
  },
];

const stats = [
  { label: "目標 Recall@3", value: "≥ 0.80", tint: "mint" as const },
  { label: "目標 Citation F1", value: "≥ 0.90", tint: "lavender" as const },
  { label: "目標 Hallucination", value: "≤ 10%", tint: "coral" as const },
];

export default function Home() {
  return (
    <main className="flex flex-col gap-24 px-6 py-12 lg:px-16 lg:py-20">
      {/* Top nav */}
      <nav className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="candy-gradient flex h-10 w-10 items-center justify-center rounded-2xl shadow-[0_8px_24px_rgba(197,163,255,0.4)]">
            <Sparkles className="h-5 w-5 text-white" />
          </div>
          <div className="flex flex-col">
            <span className="font-display text-xl font-bold text-candy-cocoa">
              明約 ClariLex
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/analyze">
            <GradientButton variant="ghost" size="sm">
              開始分析
            </GradientButton>
          </Link>
          <Link href="/eval">
            <GradientButton variant="cool" size="sm">
              評估儀表板
            </GradientButton>
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="flex flex-col items-center gap-8 text-center">
        <div className="inline-flex items-center gap-2 rounded-full bg-white/70 backdrop-blur-md px-4 py-1.5 text-sm text-candy-mocha border border-candy-pink-200/60 shadow-[0_4px_16px_rgba(255,182,217,0.2)]">
          <Sparkles className="h-3.5 w-3.5 text-candy-lavender-500" />
          <span className="font-display">
            檢索增強生成 × 法律科技
          </span>
        </div>

        <h1 className="font-display text-4xl font-bold leading-tight tracking-tight text-candy-cocoa lg:text-6xl">
          <span className="block">基於檢索增強生成技術之</span>
          <span className="block text-gradient-candy">
            租賃 ／ 買賣法律文件
          </span>
          <span className="block">智慧分析與風險評估系統</span>
        </h1>

        <p className="font-mono text-xs uppercase tracking-widest text-candy-mocha lg:text-sm">
          An Intelligent Lease &amp; Sale Legal Document Analysis and Risk Assessment System
          <br className="hidden sm:inline" />
          Based on Retrieval-Augmented Generation and Large Language Models
        </p>

        <p className="max-w-3xl text-base leading-relaxed text-candy-mocha lg:text-lg">
          系統以民法、民事訴訟法與消費者保護法為知識庫，搭配近一年司法院租賃／買賣裁判，
          對使用者上傳之合約條款進行 <span className="font-medium text-candy-cocoa">IRAC 結構化風險分析</span>，
          並以 <span className="font-medium text-candy-cocoa">跨索引三角驗證</span>、
          <span className="font-medium text-candy-cocoa">Claim-Faithfulness 主張稽核</span>、
          <span className="font-medium text-candy-cocoa">Devil&apos;s Advocate 對抗審查</span>{" "}
          三項機制量化每一句主張的忠實度，回應論文之 RQ1–RQ4。
        </p>

        <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
          <Link href="/analyze">
            <GradientButton variant="candy" size="lg">
              <Sparkles className="h-5 w-5" />
              進入系統分析頁
            </GradientButton>
          </Link>
          <Link href="/eval">
            <GradientButton variant="ghost" size="lg">
              查看評估儀表板
            </GradientButton>
          </Link>
        </div>

        <div className="mt-6 grid w-full max-w-3xl grid-cols-1 gap-4 sm:grid-cols-3">
          {stats.map((s) => (
            <CandyCard key={s.label} tint={s.tint} glow className="text-center">
              <div className="font-display text-3xl font-bold text-candy-cocoa">
                {s.value}
              </div>
              <div className="mt-1 text-sm text-candy-mocha">{s.label}</div>
            </CandyCard>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="flex flex-col gap-8">
        <div className="flex flex-col items-center gap-2 text-center">
          <h2 className="font-display text-3xl font-bold text-candy-cocoa lg:text-4xl">
            系統核心構件
          </h2>
          <p className="text-candy-mocha">
            從 OCR 到 RAG 到 Judge，整個 pipeline 都可獨立呼叫，也可一鍵跑完整流程。
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <CandyCard
              key={f.title}
              tint={f.tint}
              interactive
              glow
              className="flex flex-col gap-3"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-2xl bg-white/70 p-2.5 shadow-sm">
                  <f.icon className="h-5 w-5 text-candy-cocoa" />
                </div>
                <h3 className="font-display text-lg font-semibold text-candy-cocoa">
                  {f.title}
                </h3>
              </div>
              <p className="text-sm leading-relaxed text-candy-mocha">{f.desc}</p>
            </CandyCard>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="flex flex-col items-center gap-2 pt-12 text-sm text-candy-mocha">
        <div>
          作者：許紫晴（Hsu, Tzu-Ching）｜指導教授：張家瑋 博士（Jia-Wei Chang）
        </div>
        <div className="mt-2 text-xs">
          §5 延伸機制（Triangulator / Claim Audit / Devil&apos;s Advocate）方法論受{" "}
          <a
            href="https://github.com/Imbad0202/academic-research-skills"
            className="font-display text-candy-lavender-500 underline-offset-4 hover:underline"
          >
            Academic Research Skills
          </a>{" "}
          (Wu, 2026, CC-BY-NC 4.0) 啟發
        </div>
      </footer>
    </main>
  );
}
