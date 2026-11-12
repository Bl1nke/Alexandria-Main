"""Извлечение содержимого PDF.

Текст, координаты и признаки шрифта берутся через ``pdfplumber``;
изображения — через ``pdfplumber`` (bounding box). Если на странице нет
текста, но есть изображения, это, вероятно, скан: добавляется
предупреждение, но OCR НЕ запускается (см. config/parser_settings.OCR_ENABLED).
"""

from __future__ import annotations

from typing import Dict, List

import pdfplumber

from config.parser_settings import OCR_ENABLED
from models.document import BBox, Document, ImageRef, Page, TextBlock
from models.validation import Confidence

_LINE_TOLERANCE = 3.0


class PdfExtractor:
    """Экстрактор содержимого PDF-файлов."""

    extensions = ("pdf",)

    def extract(self, path: str) -> Document:
        """Извлекает страницы, текст и изображения PDF."""
        pages: List[Page] = []
        warnings: List[str] = []

        with pdfplumber.open(path) as pdf:
            for pdf_page in pdf.pages:
                page = self._extract_page(pdf_page)
                pages.append(page)
                if not page.has_text:
                    note = f"Страница {page.number}: текст не обнаружен"
                    if page.images:
                        note += " (вероятен скан)"
                        note += " — требуется OCR" if OCR_ENABLED else "; OCR отключён"
                    warnings.append(note)

        return Document(
            source_path=path,
            doc_type="pdf",
            pages=pages,
            metadata={"page_count": len(pages)},
            warnings=warnings,
            confidence=_document_confidence(pages),
        )

    def _extract_page(self, pdf_page) -> Page:
        return Page(
            number=pdf_page.page_number,
            width=float(pdf_page.width),
            height=float(pdf_page.height),
            blocks=self._extract_blocks(pdf_page),
            images=self._extract_images(pdf_page),
        )

    def _extract_blocks(self, pdf_page) -> List[TextBlock]:
        words = pdf_page.extract_words(extra_attrs=["fontname", "size"])
        blocks: List[TextBlock] = []
        for line_words in _group_words_by_line(words):
            text = " ".join(word["text"] for word in line_words).strip()
            if not text:
                continue
            blocks.append(
                TextBlock(
                    text=text,
                    page=pdf_page.page_number,
                    bbox=_line_bbox(line_words),
                    font_size=_line_font_size(line_words),
                    is_bold=_line_is_bold(line_words),
                )
            )
        return blocks

    def _extract_images(self, pdf_page) -> List[ImageRef]:
        images: List[ImageRef] = []
        for index, image in enumerate(pdf_page.images):
            images.append(
                ImageRef(
                    id=f"p{pdf_page.page_number}_img{index}",
                    page=pdf_page.page_number,
                    bbox=BBox(
                        x0=float(image["x0"]),
                        y0=float(image["top"]),
                        x1=float(image["x1"]),
                        y1=float(image["bottom"]),
                    ),
                )
            )
        return images


def _group_words_by_line(words: List[dict]) -> List[List[dict]]:
    """Группирует слова в строки по вертикальной координате ``top``."""
    lines: Dict[float, List[dict]] = {}
    for word in words:
        key = round(float(word["top"]) / _LINE_TOLERANCE) * _LINE_TOLERANCE
        lines.setdefault(key, []).append(word)
    return [sorted(line, key=lambda w: float(w["x0"])) for _, line in sorted(lines.items())]


def _line_bbox(words: List[dict]) -> BBox:
    return BBox(
        x0=min(float(word["x0"]) for word in words),
        y0=min(float(word["top"]) for word in words),
        x1=max(float(word["x1"]) for word in words),
        y1=max(float(word["bottom"]) for word in words),
    )


def _line_font_size(words: List[dict]) -> float:
    sizes = [float(word["size"]) for word in words if word.get("size")]
    return max(sizes) if sizes else 0.0


def _line_is_bold(words: List[dict]) -> bool:
    for word in words:
        name = str(word.get("fontname", "")).lower()
        if "bold" in name or "black" in name or "heavy" in name:
            return True
    return False


def _document_confidence(pages: List[Page]) -> Confidence:
    """Оценивает уверенность извлечения по наличию текста на страницах."""
    if not pages:
        return Confidence.LOW
    text_pages = sum(1 for page in pages if page.has_text)
    if text_pages == 0:
        return Confidence.LOW
    if text_pages < len(pages):
        return Confidence.MEDIUM
    return Confidence.HIGH
