# -*- coding: utf-8 -*-
"""產生「書背_模板.docx」—— 只有書背三方塊之空白頁,欄位可點入編輯,供他人改用。
書背 VML 直接沿用 make_spine_print.spine_pict(),與列印版完全一致(字級 12/14 級合規範)。
"""
from pathlib import Path

from docx import Document
from docx.oxml import parse_xml
from docx.shared import Cm

from make_spine_print import spine_pict

BASE = Path("/Users/ching/Desktop/taiwan-contract-risk-rag/thesis")
OUT_SPINE = BASE / "書背_模板.docx"


def main():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)   # A4 直式
    sec.left_margin, sec.right_margin = Cm(3.0), Cm(2.0)
    sec.top_margin, sec.bottom_margin = Cm(2.5), Cm(2.5)
    p = doc.add_paragraph()
    p._p.append(parse_xml(spine_pict()))
    doc.save(str(OUT_SPINE))
    print("[OK] 書背模板(可編輯,12/14 級):", OUT_SPINE.name)


if __name__ == "__main__":
    main()
