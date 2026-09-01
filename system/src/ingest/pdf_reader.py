"""PDF / 影像文件文字解析。

策略（對應論文 §3.2.3 混合式解析）：
  1. pdfplumber 嘗試提取數位文字
  2. 若 pdfplumber 提取的字數低於 `min_digital_chars`（預設 50），
     判定為掃描影像 PDF，啟動 pdf2image + Tesseract OCR (chi_tra)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pdfplumber
import pytesseract
from pdf2image import convert_from_path


_DEFAULT_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if Path(_DEFAULT_TESSERACT).exists():
    pytesseract.pytesseract.tesseract_cmd = _DEFAULT_TESSERACT


@dataclass
class ExtractedDoc:
    text: str
    source: Literal["digital", "ocr"]
    page_count: int


def _extract_digital(pdf_path: Path) -> tuple[str, int]:
    chunks: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            t = page.extract_text() or ""
            if t:
                chunks.append(t)
    return "\n".join(chunks), page_count


def _extract_ocr(pdf_path: Path, lang: str = "chi_tra+eng", dpi: int = 300) -> tuple[str, int]:
    images = convert_from_path(str(pdf_path), dpi=dpi)
    pages = [pytesseract.image_to_string(img, lang=lang) for img in images]
    return "\n".join(pages), len(images)


def extract(
    path: str | Path,
    min_digital_chars: int = 50,
    ocr_lang: str = "chi_tra+eng",
) -> ExtractedDoc:
    """Read a PDF (or text file) and return its text.

    .txt 直接讀取;圖片(JPG/PNG)走 OCR;.pdf 走數位優先 + OCR fallback 混合式策略。
    """
    p = Path(path)
    if p.suffix.lower() == ".txt":
        text = p.read_text(encoding="utf-8")
        return ExtractedDoc(text=text, source="digital", page_count=1)
    if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}:
        # 圖片(JPG/PNG 等)直接走 OCR
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(p), lang=ocr_lang)
        return ExtractedDoc(text=text, source="ocr", page_count=1)

    digital_text, pages = _extract_digital(p)
    if len(digital_text.strip()) >= min_digital_chars:
        return ExtractedDoc(text=digital_text, source="digital", page_count=pages)

    ocr_text, ocr_pages = _extract_ocr(p, lang=ocr_lang)
    return ExtractedDoc(text=ocr_text, source="ocr", page_count=ocr_pages)
