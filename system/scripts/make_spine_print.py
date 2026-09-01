# -*- coding: utf-8 -*-
"""封面左側書背(側邊,附件一規範):
版面(直排,由上而下):
  A 頂部:國立臺中科技大學(右欄)+ 資訊工程系碩士班(左欄)= 等寬並排兩直欄 (12 級)
  B 中間:碩士論文(12 級) →題目(14 級) →許紫晴 撰(12 級) = 置中單直欄,一行連貫
  C 底部:115(橫式) / 7(下一行) = 橫式數字 (12 級)
字型 標楷體-繁。字級依規範:碩士論文 12 級、論文題目 14 級。
spine_pict() 供 make_spine_only.py 共用,確保列印版與書背模板一致。
"""
import shutil
from pathlib import Path

from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import qn

BASE = Path("/Users/ching/Desktop/taiwan-contract-risk-rag/thesis")
SRC, DST = BASE / "論文_許紫晴.docx", BASE / "論文_許紫晴_列印版.docx"
FONT = ('<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" '
        'w:eastAsia="標楷體-繁" w:cs="Times New Roman"/>')
TITLE = "基於檢索增強生成技術之租賃買賣法律文件智慧分析與風險評估系統"

# 字級(w:sz = 半點, 故 12 級=24、14 級=28)
SZ_12 = 24  # 12 級:校名/系、碩士論文、撰、年月
SZ_14 = 28  # 14 級:論文中文題目


def _run(text, size):
    return (f'<w:r><w:rPr>{FONT}<w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr>'
            f'<w:t xml:space="preserve">{text}</w:t></w:r>')


def para(text, size=SZ_12, jc="center"):
    """單一字級之段落(書背一欄)。jc="distribute" 時分散對齊(首尾字貼齊欄之上下端)。"""
    return ('<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
            f'<w:jc w:val="{jc}"/></w:pPr>{_run(text, size)}</w:p>')


def para_multi(segments):
    """同一段落內多字級(供書背中欄:碩士論文12級 / 題目14級 / 撰12級 一行連貫)。
    segments = [(text, size), ...]。"""
    runs = "".join(_run(t, s) for t, s in segments)
    return ('<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
            f'<w:jc w:val="center"/></w:pPr>{runs}</w:p>')


def shape(sid, left, top, width, height, inner, vertical=True):
    flow = 'style="layout-flow:vertical-ideographic" ' if vertical else ''
    return (f'<v:shape id="{sid}" type="#_x0000_t202" '
            f'style="position:absolute;margin-left:{left}pt;margin-top:{top}pt;'
            f'width:{width}pt;height:{height}pt;'
            'mso-position-horizontal-relative:page;mso-position-vertical-relative:page;z-index:5" '
            f'filled="f" stroked="f"><v:textbox {flow}inset="0,0,0,0">'
            f'<w:txbxContent>{inner}</w:txbxContent></v:textbox></v:shape>')


def spine_pict(school="國立臺中科技大學", dept="資訊工程系碩士班",
               title=TITLE, name="許紫晴", year="115", month="7"):
    """回傳整個書背之 <w:pict>(三方塊)。字級合乎規範(校名/碩士論文/撰/年月=12 級、題目=14 級)。
    可帶參數改校名/系所/題目/姓名/年月,供不同論文重用。"""
    # A 頂部雙欄(校名右欄、系左欄),12 級。兩欄皆分散對齊 → 首尾字貼齊欄上下端,
    # 使短欄(如「資訊工程系」)之首字對齊「國」、末字對齊「學」。box 高=校名 8 字自然長(96)。
    boxA = shape("spine_head", 22, 24, 36, 96,
                 para(school, SZ_12, jc="distribute") + para(dept, SZ_12, jc="distribute"),
                 vertical=True)
    # B 中欄置中一行:碩士論文(12) →題目(14) →姓名 撰(12)
    boxB = shape("spine_body", 30, 140, 22, 650, para_multi([
        ("碩士論文", SZ_12),
        ("　　", SZ_12),
        (title, SZ_14),
        ("　　", SZ_12),
        (f"{name}　撰", SZ_12),
    ]), vertical=True)
    # C 底部橫式數字:年 / 月,12 級。left=24.7 使其橫向中心(24.7+36/2=42.7)對齊中文欄中心(x≈42.7)。
    boxC = shape("spine_year", 24.7, 792, 36, 46,
                 para(year, SZ_12) + para(month, SZ_12), vertical=False)
    return (
        '<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w10="urn:schemas-microsoft-com:office:word" '
        'xmlns:o="urn:schemas-microsoft-com:office:office"><w:pict>'
        '<v:shapetype id="_x0000_t202" coordsize="21600,21600" o:spt="202" '
        'path="m,l,21600r21600,l21600,xe"><v:stroke joinstyle="miter"/>'
        '<v:path gradientshapeok="t" o:connecttype="rect"/></v:shapetype>'
        + boxA + boxB + boxC + '</w:pict></w:r>'
    )


def main():
    shutil.copyfile(SRC, DST)
    doc = Document(str(DST))
    doc.element.body.find(qn('w:p')).append(parse_xml(spine_pict()))
    # 列印版:封面(首頁)不套浮水印(實體書封面另用卡紙印);設首頁不同→首頁 header 空白。
    # 電子版仍依規範全頁含封面皆有浮水印。
    doc.sections[0].different_first_page_header_footer = True
    doc.save(str(DST))
    print("[OK] 書背(12/14 級) + 封面免浮水印(列印版)已產生:", DST.name)


if __name__ == "__main__":
    main()
