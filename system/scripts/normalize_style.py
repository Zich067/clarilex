"""論文樣式正規化(降 AI 味 + 標點一致):
  1) 移除行內粗體 **...**(讓論述本身承載強調,符合學術體例)
  2) 將「與中日韓文字相鄰」之半形 , ; : 轉為全形 ，；：(僅中文語境;英數/參照不動)

保護不動:```程式碼圍欄```、$數學$、`行內碼`;括號 ()、小數點、英文逗號一律不碰。
用法:python scripts/normalize_style.py  → 就地修改下列檔案並印統計。
"""
from __future__ import annotations
import re
from pathlib import Path

T = Path(__file__).resolve().parents[1].parent / "thesis"
FILES = (["00_前置/中文摘要.md"] +
         [f"{n}" for n in ["01_緒論.md", "02_文獻探討.md", "03_系統設計.md",
                           "04_實作細節.md", "05_延伸機制.md", "06_實驗與結果.md", "07_結論.md"]] +
         [f"附錄/{n}" for n in ["A_System_Prompts.md", "B_API規格.md", "C_UI截圖.md",
                               "D_Gold_Standard_範例.md", "E_AI使用揭露.md", "F_系統實作與部署細節.md"]])

CJK = r"㐀-鿿豈-﫿　-〿＀-￯"  # 漢字 + 全形標點/符號
_PUNC = {",": "，", ";": "；", ":": "："}


def _protect(line):
    """抽出 $...$ 與 `...` 片段,以佔位符保護。"""
    spans = []
    def stash(m):
        spans.append(m.group(0))
        return f"\x00{len(spans)-1}\x00"
    line = re.sub(r"`[^`]*`", stash, line)
    line = re.sub(r"\$[^$]*\$", stash, line)
    return line, spans


def _restore(line, spans):
    for i, s in enumerate(spans):
        line = line.replace(f"\x00{i}\x00", s)
    return line


def conv_punct(line):
    out = []
    for i, ch in enumerate(line):
        if ch in _PUNC:
            prev = line[i-1] if i > 0 else ""
            nxt = line[i+1] if i+1 < len(line) else ""
            if re.match(f"[{CJK}]", prev) or re.match(f"[{CJK}]", nxt):
                out.append(_PUNC[ch])
                continue
        out.append(ch)
    return "".join(out)


def main():
    tot_bold = tot_punct = 0
    for rel in FILES:
        p = T / rel
        if not p.exists():
            continue
        lines = p.read_text(encoding="utf-8").splitlines(keepends=False)
        in_code = False
        new = []
        nb = npc = 0
        for ln in lines:
            if ln.lstrip().startswith("```"):
                in_code = not in_code
                new.append(ln); continue
            if in_code:
                new.append(ln); continue
            body, spans = _protect(ln)
            nb += body.count("**")
            body = body.replace("**", "")
            before = body
            body = conv_punct(body)
            npc += sum(1 for a, b in zip(before, body) if a != b)
            new.append(_restore(body, spans))
        p.write_text("\n".join(new) + "\n", encoding="utf-8")
        tot_bold += nb // 2
        tot_punct += npc
        print(f"  {rel}: 移除粗體 {nb//2} 對、標點轉全形 {npc} 處")
    print(f"[OK] 合計:粗體 {tot_bold} 對、標點 {tot_punct} 處")


if __name__ == "__main__":
    raise SystemExit(main())
