"""把論文裡的 code fence 渲染成深色 Carbon 風 PNG。

特色:
  - 視窗外框 + 左上紅黃綠三圓點(macOS 視窗感)
  - 左側行號 gutter
  - Pygments 語法上色(Dracula 配色)
  - 中英混排:ASCII 用 Menlo、中文 fallback STHeiti(等寬格點對齊,中文佔兩格)

提供 render_carbon(code, lang, out_path) 供 build_thesis_docx.py 呼叫。
也可單獨執行做 smoke test:
    python scripts/make_code_carbon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pygments import lex
from pygments.lexers import get_lexer_by_name
from pygments.lexers.special import TextLexer
from pygments.token import (
    Comment,
    Keyword,
    Name,
    Number,
    Operator,
    String,
    Token,
)
from pygments.util import ClassNotFound

# ── 字型 ──
MONO_FONT = "/System/Library/Fonts/Menlo.ttc"
CJK_FONT = "/System/Library/Fonts/STHeiti Medium.ttc"

# ── Dracula 配色 ──
BG_CARD = (33, 34, 44)        # 視窗外框
BG_CODE = (40, 42, 54)        # 程式碼區
GUTTER_FG = (98, 114, 164)    # 行號
DOT_RED = (255, 95, 86)
DOT_YELLOW = (255, 189, 46)
DOT_GREEN = (39, 201, 63)
FG_DEFAULT = (248, 248, 242)


def _color_for(tok) -> tuple[int, int, int]:
    """token type → RGB(Dracula)。"""
    if tok in Comment:
        return (98, 114, 164)
    if tok in Keyword:
        return (255, 121, 198)
    if tok in String:
        return (241, 250, 140)
    if tok in Number:
        return (189, 147, 249)
    if tok in Name.Function or tok in Name.Decorator:
        return (80, 250, 123)
    if tok in Name.Class or tok in Name.Namespace:
        return (139, 233, 253)
    if tok in Name.Builtin or tok in Name.Builtin.Pseudo:
        return (139, 233, 253)
    if tok in Operator:
        return (255, 121, 198)
    if tok in Token.Literal.String.Interpol:
        return (255, 184, 108)
    return FG_DEFAULT


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (
        0x3000 <= o <= 0x9FFF
        or 0xFF00 <= o <= 0xFFEF
        or 0x3400 <= o <= 0x4DBF
    )


def render_carbon(
    code: str,
    lang: str,
    out_path: Path,
    *,
    font_px: int = 30,
) -> Path:
    """把 code 渲染成 Carbon PNG 寫到 out_path,回傳該路徑。"""
    code = code.rstrip("\n").replace("\t", "    ")
    lines = code.split("\n")
    n = len(lines)

    mono = ImageFont.truetype(MONO_FONT, font_px)
    try:
        cjk = ImageFont.truetype(CJK_FONT, font_px)
    except OSError:
        cjk = mono

    # 等寬格寬(以 "0" 的 advance 為準)
    cw = round(mono.getlength("0"))
    ascent, descent = mono.getmetrics()
    line_h = ascent + descent + round(font_px * 0.32)

    pad = round(font_px * 0.9)
    titlebar = round(font_px * 1.5)
    gutter_digits = len(str(n))
    gutter_w = (gutter_digits + 1) * cw + pad // 2

    max_cols = 0
    for ln in lines:
        cols = sum(2 if _is_cjk(c) else 1 for c in ln)
        max_cols = max(max_cols, cols)
    code_w = max_cols * cw + cw  # 尾端留一格

    W = pad + gutter_w + code_w + pad
    H = titlebar + pad // 2 + n * line_h + pad

    img = Image.new("RGB", (W, H), BG_CARD)
    draw = ImageDraw.Draw(img)

    # 程式碼底色區(留出 titlebar)
    draw.rectangle([0, titlebar, W, H], fill=BG_CODE)

    # 視窗三圓點
    r = round(font_px * 0.22)
    cy = titlebar // 2
    cx = pad + r
    for col in (DOT_RED, DOT_YELLOW, DOT_GREEN):
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
        cx += round(r * 3.2)

    # lexer
    try:
        lexer = get_lexer_by_name(lang) if lang and lang != "text" else TextLexer()
    except ClassNotFound:
        lexer = TextLexer()

    y = titlebar + pad // 2
    x0 = pad + gutter_w
    for idx, raw in enumerate(lines, 1):
        # 行號(靠右對齊)
        num = str(idx)
        nx = pad + (gutter_digits - len(num)) * cw
        draw.text((nx, y), num, font=mono, fill=GUTTER_FG)

        # 該行 token 上色:對每行重新 lex 會錯亂多行 string,故整段 lex 後依 \n 切。
        x = x0
        for ch, col in _line_tokens(lexer, code, idx):
            f = cjk if _is_cjk(ch) else mono
            draw.text((x, y), ch, font=f, fill=col)
            x += cw * (2 if _is_cjk(ch) else 1)
        y += line_h

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


# 整段 lex 一次,快取成 {行號: [(char, rgb)]}
_TOKEN_CACHE: dict[int, list[tuple[str, tuple[int, int, int]]]] = {}
_CACHE_KEY: tuple[int, str] | None = None


def _line_tokens(lexer, code: str, line_no: int):
    """回傳指定行的 [(char, rgb)]。整段只 lex 一次並快取。"""
    global _CACHE_KEY, _TOKEN_CACHE
    key = (id(lexer), code)
    if _CACHE_KEY != key:
        _TOKEN_CACHE = {}
        cur = 1
        _TOKEN_CACHE[cur] = []
        for tok, text in lex(code, lexer):
            col = _color_for(tok)
            for ch in text:
                if ch == "\n":
                    cur += 1
                    _TOKEN_CACHE[cur] = []
                else:
                    _TOKEN_CACHE.setdefault(cur, []).append((ch, col))
        _CACHE_KEY = key
    return _TOKEN_CACHE.get(line_no, [])


if __name__ == "__main__":
    sample = (
        "def retrieve(query: str, top_k: int = 3):\n"
        "    # 以多語 MiniLM 編碼後查 ChromaDB(雙索引)\n"
        '    emb = model.encode(query)\n'
        "    hits = collection.query(emb, n_results=top_k)\n"
        "    return [Doc(id=h.id, score=h.dist) for h in hits]\n"
    )
    out = Path(__file__).resolve().parents[1].parent / "thesis" / "figures" / "code" / "_smoke.png"
    render_carbon(sample, "python", out)
    print("[OK] wrote", out, out.stat().st_size, "bytes")
