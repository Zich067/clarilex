"""把 LaTeX 數學式渲染成期刊級 PNG(matplotlib mathtext,無需系統 LaTeX)。

供 build_thesis_docx.py 處理 markdown 中的 $$...$$ 顯示公式。
提供 render_math(latex, out_path) 回傳該路徑與像素寬高。
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams["mathtext.fontset"] = "cm"  # Computer Modern,期刊數學字體


def render_math(latex: str, out_path: Path, *, fontsize: int = 22, dpi: int = 220) -> tuple[Path, int, int]:
    """渲染單行 LaTeX 數學式為 PNG。latex 不含外層 $。"""
    expr = latex.strip()
    if not (expr.startswith("$") and expr.endswith("$")):
        expr = f"${expr}$"
    fig = plt.figure(figsize=(0.1, 0.1))
    t = fig.text(0, 0, expr, fontsize=fontsize, color="black", ha="left", va="bottom")
    fig.canvas.draw()
    bbox = t.get_window_extent()
    w_in = bbox.width / fig.dpi + 0.1
    h_in = bbox.height / fig.dpi + 0.1
    fig.set_size_inches(w_in, h_in)
    t.set_position((0.05 / w_in, 0.05 / h_in))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, transparent=False, facecolor="white", bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    from PIL import Image

    with Image.open(out_path) as im:
        w_px, h_px = im.size
    return out_path, w_px, h_px


if __name__ == "__main__":
    samples = [
        r"s(q,c)=\cos(\phi(q),\phi(c))+\lambda\,\mathbb{1}[\mathrm{art}(q)\cap\mathrm{art}(c)\neq\emptyset]",
        r"\mathrm{Faithfulness}=\dfrac{n_{\mathrm{sup}}+0.5\,n_{\mathrm{par}}}{n_{\mathrm{sup}}+n_{\mathrm{par}}+n_{\mathrm{uns}}}",
        r"\mathrm{nDCG}@K=\dfrac{\mathrm{DCG}@K}{\mathrm{IDCG}@K},\quad \mathrm{DCG}@K=\sum_{i=1}^{K}\dfrac{rel_i}{\log_2(i+1)}",
    ]
    base = Path(__file__).resolve().parents[1].parent / "thesis" / "figures" / "math"
    for i, s in enumerate(samples):
        p, w, h = render_math(s, base / f"_smoke_{i}.png")
        print(f"[OK] {p.name}  {w}x{h}")
