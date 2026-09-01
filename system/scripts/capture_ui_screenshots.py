"""附錄 C 實機 UI 截圖：以 Playwright 驅動真實前端（:3000）+ 後端（:8000）。

流程全為真實互動，非靜態渲染：
  /analyze → 上傳 sample_lease.pdf → 點「開始分析」(SSE 真實 gpt-5-mini)
           → 選高風險條款 → 截圖
  → 點「看評估儀表板」(client 端導航，保留 store) → /eval 跑真實 judge/devil → 截圖
  → 首頁 → 截圖

用已安裝之 Google Chrome（channel=chrome），免下載 chromium。
輸出：thesis/figures/screenshots/{home,analyze,eval}.png
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data" / "samples" / "sample_lease.pdf"
OUT = ROOT.parent / "thesis" / "figures" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:3000"

TARGET_CLAUSE = "第三條"  # 租金及押金（high 風險，與 C.3 逐字範例一致）


def run() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1480, "height": 2200},
                                device_scale_factor=2)
        page.set_default_timeout(30000)

        # ── /analyze ──
        page.goto(f"{BASE}/analyze", wait_until="networkidle")
        # 等後端 live（dropzone 可用 + 健康檢查）
        page.wait_for_selector('input[type="file"]', state="attached")
        page.wait_for_timeout(1500)

        # 上傳 PDF（react-dropzone 的隱藏 input）
        page.set_input_files('input[type="file"]', str(PDF))
        # 等條款切出（左側出現第一條按鈕）
        page.wait_for_selector("text=第一條", timeout=30000)
        print("uploaded, clauses listed")

        # 切換為 RAG 模式（與逐字輸出一致）
        try:
            page.get_by_role("button", name="RAG", exact=True).click()
            page.wait_for_timeout(400)
        except PWTimeout:
            print("warn: 找不到 RAG 模式鈕，沿用預設模式")

        # 點「開始分析」（SSE 逐條串流）
        page.get_by_role("button", name=re.compile("開始分析")).click()
        # 第三條 = clause index 2，串流跑到「分析中 3/8」即代表前三條已完成。
        # 不等全部 8 條：後段曾偶發 gpt-5-mini 逾時造成 SSE abort（abort 會清掉
        # store → IRAC 消失、條款列表歸零）。故抓到目標條款就早退、立刻導去 eval
        # （client 端乾淨關閉串流），避開尾端 abort。
        try:
            page.wait_for_function(
                "() => { const m=document.body.innerText.match(/分析中\\s*(\\d+)\\s*\\/\\s*\\d+/);"
                " return m && parseInt(m[1]) >= 3; }",
                timeout=300000,
            )
            print("前三條（含第三條）已分析完成")
        except PWTimeout:
            print("warn: 等不到『分析中 3/8』，仍續行")
        page.wait_for_timeout(600)

        # 選第三條（高風險，與 C.3 逐字範例一致）
        try:
            btn = page.locator("aside button", has_text=TARGET_CLAUSE).first
            btn.scroll_into_view_if_needed()
            btn.click()
        except PWTimeout:
            print(f"warn: 找不到 {TARGET_CLAUSE}，用預設選中條款")
        # 等該條款 IRAC 報告 render（currentAnalysis 就緒）
        try:
            page.wait_for_selector("text=IRAC 風險分析", timeout=60000)
            print("IRAC 報告已出現")
        except PWTimeout:
            print("warn: 未見 IRAC 標題，仍截圖")
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "analyze.png"), full_page=True)
        print("[ok] analyze.png")

        # ── /eval（client 端導航以保留 zustand store）──
        link = page.locator("a", has_text="看評估儀表板").first
        link.scroll_into_view_if_needed()
        link.click()
        page.wait_for_url(re.compile(r"/eval"), timeout=30000)
        # 正向斷言兩軌結果內容出現（比等 spinner 消失穩）：
        #   judge → 獨有的「Reasoning Sim.」環標籤（mock 對照表沒有此字）
        #   devil → 獨有的「Round 1」回合卡（store 有 analysis 才會 render）
        try:
            page.wait_for_function(
                "() => { const t=document.body.innerText;"
                " return t.includes('Reasoning Sim.') && /Round\\s*1/.test(t); }",
                timeout=300000,
            )
            print("eval: judge & devil 結果已出現")
        except PWTimeout:
            print("warn: eval judge/devil 結果未出現，仍截圖")
        # 殘餘的 spinner 字樣保險再等一次（避免某軌仍在 refetch）
        try:
            page.wait_for_function(
                "() => { const t=document.body.innerText;"
                " return !t.includes('跑 LLM-as-Judge 中')"
                " && !t.includes('魔鬼代言人正在找碴'); }",
                timeout=120000,
            )
        except PWTimeout:
            print("warn: 仍有 spinner 字樣殘留")
        page.wait_for_timeout(3000)
        page.screenshot(path=str(OUT / "eval.png"), full_page=True)
        print("[ok] eval.png")

        # ── 首頁 ──
        page.goto(f"{BASE}/", wait_until="networkidle")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(OUT / "home.png"), full_page=True)
        print("[ok] home.png")

        browser.close()


if __name__ == "__main__":
    try:
        run()
    except Exception as e:  # noqa: BLE001
        print("ERROR:", e)
        sys.exit(1)
