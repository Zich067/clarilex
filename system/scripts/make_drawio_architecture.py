"""產生漂亮的 drawio 架構圖 (.drawio XML)。

設計重點:
  - 4 Phase 區塊以淡色長矩形包裹,標頭加深色 chip
  - 各步驟為圓角矩形,延伸機制 (Triangulator / Claim Audit / Devil's Advocate)
    額外加 ★ + sky 配色突顯
  - 知識庫為兩個 cylinder shape (LAWS + JUDGEMENTS),底部置中
  - 箭頭風格:雙線粗細,Phase 間銜接用主箭頭、KB→Triangulator 用虛線

輸出:
  thesis/figures/fig_architecture.drawio       (XML source,可在 drawio 開啟編輯)
  thesis/figures/fig_architecture.png          (由 drawio CLI 匯出)

用法:
    python scripts/make_drawio_architecture.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree, tostring
from xml.dom import minidom

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT.parent / "thesis" / "figures"
DRAWIO_OUT = FIG_DIR / "fig_architecture.drawio"
PNG_OUT = FIG_DIR / "fig_architecture.png"

DRAWIO_BIN = "/Applications/draw.io.app/Contents/MacOS/draw.io"

# ─── 糖果色 ───
COLORS = {
    "pink": {"bg": "#FFE1EE", "border": "#FF8FC2", "chip": "#FFB6D9", "chip_text": "#B83465"},
    "lavender": {"bg": "#EFE6FF", "border": "#9670EC", "chip": "#C5A3FF", "chip_text": "#6B3FCC"},
    "mint": {"bg": "#E9FAF2", "border": "#5EC99F", "chip": "#A8E6CF", "chip_text": "#2E8B6F"},
    "coral": {"bg": "#FFE1E4", "border": "#EE5C69", "chip": "#FF8B94", "chip_text": "#A82B3A"},
    "sky": {"bg": "#E6F3FF", "border": "#5FB0EE", "chip": "#A4D8FF", "chip_text": "#2C6FB8"},
    "lemon": {"bg": "#FFF8DF", "border": "#F5C451", "chip": "#FFE39E", "chip_text": "#8A6F1A"},
    "cocoa": "#3D2C2A",
    "mocha": "#6B524F",
}


class CellBuilder:
    def __init__(self):
        self.cells: list[tuple[str, dict]] = []
        self._next = 2  # 0 / 1 reserved

    def _id(self) -> str:
        n = f"n{self._next}"
        self._next += 1
        return n

    def add_vertex(
        self,
        value: str,
        x: int,
        y: int,
        w: int,
        h: int,
        *,
        style: str,
        parent: str = "1",
    ) -> str:
        cid = self._id()
        self.cells.append(
            (
                cid,
                {
                    "value": value,
                    "style": style,
                    "vertex": "1",
                    "parent": parent,
                    "geom": (x, y, w, h),
                },
            )
        )
        return cid

    def add_edge(
        self,
        source: str,
        target: str,
        *,
        style: str = "endArrow=classic;html=1;rounded=0;strokeColor=#3D2C2A;strokeWidth=2;",
        parent: str = "1",
        label: str = "",
    ) -> str:
        cid = self._id()
        self.cells.append(
            (
                cid,
                {
                    "value": label,
                    "style": style,
                    "edge": "1",
                    "source": source,
                    "target": target,
                    "parent": parent,
                },
            )
        )
        return cid

    def to_xml(self, page_w: int, page_h: int) -> str:
        mxfile = Element("mxfile", host="Electron", agent="custom", version="30.0.2", type="device")
        diagram = SubElement(mxfile, "diagram", id="arch01", name="完整架構圖")
        model = SubElement(
            diagram,
            "mxGraphModel",
            dx="1200",
            dy="800",
            grid="1",
            gridSize="10",
            guides="1",
            tooltips="1",
            connect="1",
            arrows="1",
            fold="1",
            page="1",
            pageScale="1",
            pageWidth=str(page_w),
            pageHeight=str(page_h),
            math="0",
            shadow="0",
        )
        root = SubElement(model, "root")
        SubElement(root, "mxCell", id="0")
        SubElement(root, "mxCell", id="1", parent="0")

        for cid, props in self.cells:
            cell = SubElement(
                root,
                "mxCell",
                id=cid,
                value=props["value"],
                style=props["style"],
                parent=props["parent"],
            )
            if props.get("vertex"):
                cell.set("vertex", "1")
                x, y, w, h = props["geom"]
                SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), attrib={"as": "geometry"})
            elif props.get("edge"):
                cell.set("edge", "1")
                if props.get("source"):
                    cell.set("source", props["source"])
                if props.get("target"):
                    cell.set("target", props["target"])
                geom = SubElement(cell, "mxGeometry", relative="1", attrib={"as": "geometry"})

        rough = tostring(mxfile, encoding="utf-8").decode("utf-8")
        pretty = minidom.parseString(rough).toprettyxml(indent="  ")
        # 移除 XML 宣告自動加的多餘空白
        lines = [line for line in pretty.splitlines() if line.strip()]
        return "\n".join(lines)


# ─── 樣式 helpers ───


def phase_block_style(color_key: str) -> str:
    c = COLORS[color_key]
    return (
        f"rounded=1;whiteSpace=wrap;html=1;fillColor={c['bg']};strokeColor={c['border']};"
        f"strokeWidth=2;fontSize=10;dashed=1;dashPattern=8 4;opacity=80;"
    )


def phase_chip_style(color_key: str) -> str:
    c = COLORS[color_key]
    return (
        f"rounded=1;whiteSpace=wrap;html=1;fillColor={c['chip']};strokeColor={c['border']};"
        f"strokeWidth=2;fontSize=14;fontStyle=1;fontColor={c['chip_text']};"
        f"shadow=0;arcSize=30;"
    )


def step_box_style(color_key: str, highlight: bool = False) -> str:
    """步驟方格;highlight=True 用 sky 配色突顯 (延伸機制)。"""
    c = COLORS["sky"] if highlight else COLORS[color_key]
    bg = c["bg"]
    border = c["border"]
    return (
        f"rounded=1;whiteSpace=wrap;html=1;fillColor={bg};strokeColor={border};"
        f"strokeWidth=2;fontSize=11;fontStyle=1;fontColor={COLORS['cocoa']};"
        f"shadow=1;arcSize=20;align=center;verticalAlign=middle;"
    )


def db_style() -> str:
    c = COLORS["lemon"]
    return (
        f"shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;"
        f"size=15;fillColor={c['chip']};strokeColor={c['border']};strokeWidth=2;"
        f"fontSize=11;fontStyle=1;fontColor={COLORS['cocoa']};"
    )


def kb_collection_style(color_key: str) -> str:
    c = COLORS[color_key]
    return (
        f"shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;size=15;"
        f"fillColor=white;strokeColor={c['border']};strokeWidth=2;fontSize=10;"
        f"fontStyle=1;fontColor={c['border']};"
    )


def title_style() -> str:
    return (
        f"text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;"
        f"whiteSpace=wrap;rounded=0;fontSize=18;fontStyle=1;fontColor={COLORS['cocoa']};"
    )


def subtitle_style() -> str:
    return (
        f"text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;"
        f"whiteSpace=wrap;rounded=0;fontSize=11;fontColor={COLORS['mocha']};"
    )


def edge_solid_style(color: str = "#3D2C2A") -> str:
    return f"endArrow=classic;html=1;rounded=0;strokeColor={color};strokeWidth=2;endFill=1;"


def edge_dashed_style(color: str) -> str:
    return (
        f"endArrow=classic;html=1;rounded=0;strokeColor={color};strokeWidth=1.5;endFill=1;"
        f"dashed=1;dashPattern=6 4;"
    )


# ─── 主結構 ───


def main() -> int:
    cb = CellBuilder()

    PAGE_W = 1700
    PAGE_H = 1180

    # 標題
    cb.add_vertex(
        "圖 3.1  租賃／買賣法律文件智慧分析與風險評估系統 — 完整架構",
        80,
        20,
        PAGE_W - 160,
        40,
        style=title_style(),
    )
    cb.add_vertex(
        "Phase I → IV｜★ 標記之區塊為本研究於 §5 提出之延伸機制 (Triangulator / Claim-Faithfulness Audit / Devil's Advocate)",
        80,
        62,
        PAGE_W - 160,
        24,
        style=subtitle_style(),
    )

    # Phase 背景框 (淡虛線)
    phase_y = 100
    phase_h = 680
    phase_col_w = 380
    phase_gap = 30
    phase_xs = [60, 60 + (phase_col_w + phase_gap), 60 + 2 * (phase_col_w + phase_gap), 60 + 3 * (phase_col_w + phase_gap)]

    for x, key in zip(phase_xs, ["pink", "lavender", "mint", "coral"]):
        cb.add_vertex("", x, phase_y, phase_col_w, phase_h, style=phase_block_style(key))

    # Phase chips (標頭)
    chip_labels = [
        ("Phase I", "輸入與預處理", "pink"),
        ("Phase II", "RAG 核心檢索 + Triangulator", "lavender"),
        ("Phase III", "CoT 推理與輸出", "mint"),
        ("Phase IV", "LLM-as-Judge 評估 + 對抗審查", "coral"),
    ]
    for x, (title, sub, key) in zip(phase_xs, chip_labels):
        cb.add_vertex(
            f"<b>{title}</b><br><span style='font-size:10px'>{sub}</span>",
            x + 20,
            phase_y + 18,
            phase_col_w - 40,
            56,
            style=phase_chip_style(key),
        )

    # 步驟卡片 helper
    step_w = phase_col_w - 60
    step_h = 80
    step_x_offset = 30

    def add_step(
        phase_idx: int,
        row: int,
        title: str,
        subtitle: str,
        *,
        color_key: str = None,
        highlight: bool = False,
    ) -> str:
        x = phase_xs[phase_idx] + step_x_offset
        y = phase_y + 100 + row * (step_h + 25)
        if color_key is None:
            color_key = ["pink", "lavender", "mint", "coral"][phase_idx]
        value = (
            f"<div style='font-weight:bold;font-size:12px;'>{title}</div>"
            f"<div style='font-size:9.5px;color:#6B524F;margin-top:4px;'>{subtitle}</div>"
        )
        return cb.add_vertex(value, x, y, step_w, step_h, style=step_box_style(color_key, highlight))

    # ── Phase I: 1 → 4 ──
    p1_steps = [
        ("1. 文件上傳", "PDF / 圖檔 + Query"),
        ("2. 文件類型判斷", "掃描檔 ／ 數位文本"),
        ("3. 文件解析", "pdfplumber → Tesseract"),
        ("4. 文本清洗與切片", "smart_split · JSON 結構化"),
    ]
    p1_ids = [add_step(0, i, t, s) for i, (t, s) in enumerate(p1_steps)]
    for i in range(len(p1_ids) - 1):
        cb.add_edge(p1_ids[i], p1_ids[i + 1], style=edge_solid_style(COLORS["pink"]["border"]))

    # ── Phase II: 5 → 8 ──
    p2_steps = [
        ("5. 向量化 Embedding", "MiniLM-L12-v2 · 384 維"),
        ("★ 6. Triangulator", "LAWS ⊕ JUDGEMENTS 雙索引 · §5.2", True),
        ("7. 提取 Context", "Top-K + cross_corroborated"),
        ("8. 提示工程 Prompt", "Persona + IRAC + CoT"),
    ]
    p2_ids = []
    for i, item in enumerate(p2_steps):
        if len(item) == 3:
            t, s, hl = item
            p2_ids.append(add_step(1, i, t, s, highlight=True))
        else:
            t, s = item
            p2_ids.append(add_step(1, i, t, s))
    for i in range(len(p2_ids) - 1):
        cb.add_edge(p2_ids[i], p2_ids[i + 1], style=edge_solid_style(COLORS["lavender"]["border"]))

    # Phase I → Phase II 銜接
    cb.add_edge(p1_ids[0], p2_ids[0], style=edge_solid_style())

    # ── Phase III: 9 → 11 ──
    p3_steps = [
        ("9. LLM 推理", "gpt-5-mini · reasoning_effort=low"),
        ("10. 結構化報告生成", "IRAC + 風險等級 + 建議"),
        ("11. 結果呈現 (Web UI)", "Next.js + SSE 串流"),
    ]
    p3_ids = [add_step(2, i, t, s) for i, (t, s) in enumerate(p3_steps)]
    for i in range(len(p3_ids) - 1):
        cb.add_edge(p3_ids[i], p3_ids[i + 1], style=edge_solid_style(COLORS["mint"]["border"]))

    cb.add_edge(p2_ids[0], p3_ids[0], style=edge_solid_style())

    # ── Phase IV: ① → ④ ──
    p4_steps = [
        ("① Citation Accuracy", "條號精準匹配 P/R/F1"),
        ("★ ② Claim-Faithfulness Audit", "原子主張稽核 · §5.3", True),
        ("★ ③ Devil's Advocate", "三輪對抗審查 · §5.4", True),
        ("④ 評分與報告輸出", "Faithfulness · F1 · Robustness"),
    ]
    p4_ids = []
    for i, item in enumerate(p4_steps):
        if len(item) == 3:
            t, s, hl = item
            p4_ids.append(add_step(3, i, t, s, highlight=True))
        else:
            t, s = item
            p4_ids.append(add_step(3, i, t, s))
    for i in range(len(p4_ids) - 1):
        cb.add_edge(p4_ids[i], p4_ids[i + 1], style=edge_solid_style(COLORS["coral"]["border"]))

    cb.add_edge(p3_ids[0], p4_ids[0], style=edge_solid_style())

    # ── 知識庫 ──
    kb_y = phase_y + phase_h + 30
    kb_box_x = 350
    kb_box_w = 1000
    kb_box_h = 140
    cb.add_vertex(
        f"<b>知識庫 (ChromaDB · cosine · K=3)</b>",
        kb_box_x,
        kb_y,
        kb_box_w,
        40,
        style=(
            f"rounded=1;whiteSpace=wrap;html=1;fillColor={COLORS['lemon']['bg']};"
            f"strokeColor={COLORS['lemon']['border']};strokeWidth=2;fontSize=13;fontStyle=1;"
            f"fontColor={COLORS['cocoa']};arcSize=20;"
        ),
    )
    laws_id = cb.add_vertex(
        f"<b>LAWS collection</b><br><span style='font-size:9.5px'>全國法規資料庫<br>民法／民訴／消保法<br>2,429 條 chunk</span>",
        kb_box_x + 60,
        kb_y + 55,
        380,
        70,
        style=kb_collection_style("lavender"),
    )
    judg_id = cb.add_vertex(
        f"<b>JUDGEMENTS collection</b><br><span style='font-size:9.5px'>司法院 OpenData<br>民國 110–114 年<br>9+ chunks</span>",
        kb_box_x + 560,
        kb_y + 55,
        380,
        70,
        style=kb_collection_style("sky"),
    )

    # KB → Triangulator (虛線)
    cb.add_edge(
        laws_id,
        p2_ids[1],
        style=edge_dashed_style(COLORS["lavender"]["border"]),
        label="laws hits",
    )
    cb.add_edge(
        judg_id,
        p2_ids[1],
        style=edge_dashed_style(COLORS["sky"]["border"]),
        label="judg. hits",
    )

    # ── 圖例 ──
    legend_y = kb_y + kb_box_h + 30
    legend_items = [
        ("Phase I", "pink"),
        ("Phase II + Triangulator", "lavender"),
        ("Phase III", "mint"),
        ("Phase IV + 延伸", "coral"),
        ("★ §5 延伸機制", "sky"),
        ("知識庫", "lemon"),
    ]
    leg_x = 80
    for label, key in legend_items:
        c = COLORS[key]
        cb.add_vertex(
            "",
            leg_x,
            legend_y,
            20,
            20,
            style=(
                f"rounded=1;whiteSpace=wrap;html=1;fillColor={c['chip']};"
                f"strokeColor={c['border']};strokeWidth=1.5;arcSize=30;"
            ),
        )
        cb.add_vertex(
            label,
            leg_x + 28,
            legend_y - 3,
            220,
            26,
            style=(
                f"text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;"
                f"fontSize=10;fontColor={COLORS['cocoa']};"
            ),
        )
        leg_x += 260

    # ── 寫檔 ──
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    xml = cb.to_xml(PAGE_W, PAGE_H)
    DRAWIO_OUT.write_text(xml, encoding="utf-8")
    print(f"[OK] drawio XML 寫入 {DRAWIO_OUT}")

    # ── 用 drawio CLI 匯 PNG ──
    if Path(DRAWIO_BIN).exists():
        print(f"[*] 用 drawio 匯出 PNG…")
        proc = subprocess.run(
            [DRAWIO_BIN, "-x", "-f", "png", "-o", str(PNG_OUT), str(DRAWIO_OUT), "--scale", "2", "-b", "20"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if PNG_OUT.exists():
            print(f"[OK] PNG 匯出 {PNG_OUT}  ({PNG_OUT.stat().st_size // 1024} KB)")
        else:
            print(f"[!] PNG 匯出失敗:")
            print(proc.stdout[-500:])
            print(proc.stderr[-500:])
    else:
        print(f"[!] 找不到 drawio: {DRAWIO_BIN}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
