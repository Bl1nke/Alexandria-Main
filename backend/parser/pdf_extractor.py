"""Извлечение содержимого PDF.

Движок — PyMuPDF (``pymupdf``). Один проход по документу даёт текстовые
блоки с координатами и признаками шрифта, таблицы со структурой строк и
столбцов, а также встроенные изображения вместе с их исходным форматом.
Порядок извлечения и координаты сохраняются как есть: адаптивный анализ
колонок выполняют последующие этапы, а не этот экстрактор.

Страницы без текстового слоя (сканы) помечаются ``needs_ocr = True``, но
OCR не запускается (см. config/parser_settings.OCR_ENABLED).
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import pymupdf

from config.parser_settings import (
    IMAGE_DEFAULT_EXTENSION,
    IMAGE_FORMATS,
    OCR_MIN_CHARS_PER_PAGE,
)
from models.document import BBox, Document, ImageRef, Page, Table, TableCell, TextBlock
from models.validation import Confidence
from parser.document_loader import DocumentReadError

# Биты флагов шрифта в span["flags"] (см. документацию PyMuPDF):
#   2 — курсив, 16 — полужирный.
_FLAG_ITALIC = 1 << 1
_FLAG_BOLD = 1 << 4


class PdfExtractor:
    """Экстрактор содержимого PDF-файлов (движок PyMuPDF)."""

    extensions = ("pdf",)

    def extract(self, path: str, *, image_dir: Optional[str] = None) -> Document:
        """Извлекает страницы, текст, таблицы и изображения PDF.

        Args:
            path: путь к PDF-файлу.
            image_dir: каталог для сохранения встроенных изображений. Если
                ``None``, изображения не записываются (формат и координаты
                всё равно определяются).

        Raises:
            DocumentReadError: файл не открывается или не содержит страниц.
        """
        warnings: List[str] = []
        errors: List[str] = []
        pages: List[Page] = []

        try:
            pdf = pymupdf.open(path)
        except Exception as exc:  # noqa: BLE001
            raise DocumentReadError(
                f"Не удалось открыть PDF «{os.path.basename(path)}»: {exc}"
            ) from exc

        with pdf:
            if pdf.page_count == 0:
                raise DocumentReadError(
                    f"PDF «{os.path.basename(path)}» не содержит страниц"
                )
            if image_dir is not None:
                os.makedirs(image_dir, exist_ok=True)
            # Кэш сохранённых изображений по xref: один файл на изображение,
            # даже если оно размещено на странице несколько раз.
            saved: Dict[int, Tuple[Optional[str], Optional[str], Optional[int], Optional[int]]] = {}
            for page in pdf:
                extracted = self._extract_page(pdf, page, image_dir, saved, errors)
                pages.append(extracted)
                if extracted.needs_ocr:
                    note = (
                        f"Страница {extracted.number}: текстовый слой отсутствует "
                        f"или неполон"
                    )
                    if extracted.has_images:
                        note += " (вероятен скан)"
                    note += " — требуется OCR"
                    warnings.append(note)

        return Document(
            source_path=path,
            doc_type="pdf",
            pages=pages,
            metadata={"page_count": len(pages), "image_dir": image_dir},
            warnings=warnings,
            errors=errors,
            confidence=_document_confidence(pages),
        )

    def _extract_page(
        self,
        pdf,
        page,
        image_dir: Optional[str],
        saved: Dict[int, Tuple],
        errors: List[str],
    ) -> Page:
        number = page.number + 1
        blocks = self._extract_blocks(page, number)
        tables = self._extract_tables(page, number)
        images = self._extract_images(pdf, page, number, image_dir, saved, errors)
        text_chars = sum(len(block.text) for block in blocks)
        return Page(
            number=number,
            width=float(page.rect.width),
            height=float(page.rect.height),
            blocks=blocks,
            images=images,
            tables=tables,
            needs_ocr=text_chars < OCR_MIN_CHARS_PER_PAGE,
        )

    def _extract_blocks(self, page, number: int) -> List[TextBlock]:
        """Собирает текстовые блоки страницы, сохраняя порядок извлечения."""
        raw_blocks = page.get_text("dict").get("blocks", [])
        blocks: List[TextBlock] = []
        index = 0
        for raw in raw_blocks:
            if raw.get("type") != 0:  # 0 — текст, 1 — изображение
                continue
            text, spans = _collect_block_text(raw)
            if not text:
                continue
            blocks.append(
                TextBlock(
                    text=text,
                    page=number,
                    bbox=_bbox(raw.get("bbox")),
                    font_size=_dominant_font_size(spans),
                    font_name=_dominant_font_name(spans),
                    is_bold=_any_flag(spans, _FLAG_BOLD),
                    is_italic=_any_flag(spans, _FLAG_ITALIC),
                    id=f"p{number}_b{index}",
                    block_type="paragraph",
                    source="pdf",
                    extraction_index=index,
                )
            )
            index += 1
        return blocks

    def _extract_tables(self, page, number: int) -> List[Table]:
        """Извлекает таблицы страницы с сохранением структуры строк и столбцов."""
        try:
            finder = page.find_tables()
        except Exception:  # noqa: BLE001 — детект таблиц не критичен
            return []
        tables: List[Table] = []
        for t_index, table in enumerate(getattr(finder, "tables", None) or []):
            rows = _rows_from_table(table)
            if not rows:
                continue
            tables.append(
                Table(
                    id=f"p{number}_t{t_index}",
                    page=number,
                    bbox=_bbox(getattr(table, "bbox", None)),
                    rows=rows,
                    source="pdf",
                )
            )
        return tables

    def _extract_images(
        self,
        pdf,
        page,
        number: int,
        image_dir: Optional[str],
        saved: Dict[int, Tuple],
        errors: List[str],
    ) -> List[ImageRef]:
        """Извлекает встроенные изображения страницы (по размещениям)."""
        images: List[ImageRef] = []
        index = 0
        for info in page.get_images(full=True):
            xref = info[0]
            path, fmt, width, height = _resolve_saved_image(
                pdf, xref, image_dir, saved, errors
            )
            rects = page.get_image_rects(xref) or []
            if not rects:
                # Координаты недоступны — не выдумываем их (bbox=None).
                images.append(
                    ImageRef(
                        id=f"p{number}_img{index}",
                        page=number,
                        path=path,
                        format=fmt,
                        width=width,
                        height=height,
                    )
                )
                index += 1
                continue
            for rect in rects:
                images.append(
                    ImageRef(
                        id=f"p{number}_img{index}",
                        page=number,
                        bbox=BBox(
                            x0=float(rect.x0),
                            y0=float(rect.y0),
                            x1=float(rect.x1),
                            y1=float(rect.y1),
                        ),
                        path=path,
                        format=fmt,
                        width=width,
                        height=height,
                    )
                )
                index += 1
        return images


def _collect_block_text(raw_block: dict) -> Tuple[str, List[dict]]:
    """Собирает текст блока (по строкам) и список его span'ов."""
    parts: List[str] = []
    spans: List[dict] = []
    for line in raw_block.get("lines", []):
        line_spans = line.get("spans", [])
        line_text = "".join(str(span.get("text", "")) for span in line_spans)
        if line_text.strip():
            parts.append(line_text.strip())
        spans.extend(line_spans)
    return "\n".join(parts).strip(), spans


def _bbox(raw) -> Optional[BBox]:
    """Преобразует кортеж координат PyMuPDF в :class:`BBox`."""
    if not raw:
        return None
    x0, y0, x1, y1 = raw
    return BBox(x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1))


def _dominant_font_size(spans: List[dict]) -> float:
    sizes = [float(span["size"]) for span in spans if span.get("size")]
    return max(sizes) if sizes else 0.0


def _dominant_font_name(spans: List[dict]) -> Optional[str]:
    for span in spans:
        name = span.get("font")
        if name:
            return str(name)
    return None


def _any_flag(spans: List[dict], flag: int) -> bool:
    return any(int(span.get("flags", 0)) & flag for span in spans)


def _rows_from_table(table) -> List[List[TableCell]]:
    """Превращает таблицу PyMuPDF в строки :class:`TableCell`."""
    raw_rows = table.extract() or []
    rows_meta = getattr(table, "rows", None) or []
    rows: List[List[TableCell]] = []
    for r, raw_row in enumerate(raw_rows):
        row_cells = getattr(rows_meta[r], "cells", None) if r < len(rows_meta) else None
        cells: List[TableCell] = []
        for c, value in enumerate(raw_row):
            cell_bbox = None
            if row_cells and c < len(row_cells) and row_cells[c]:
                cell_bbox = _bbox(row_cells[c])
            cells.append(
                TableCell(
                    row=r,
                    col=c,
                    text=(value or "").strip(),
                    bbox=cell_bbox,
                )
            )
        rows.append(cells)
    return rows


def _resolve_saved_image(
    pdf,
    xref: int,
    image_dir: Optional[str],
    saved: Dict[int, Tuple],
    errors: List[str],
) -> Tuple[Optional[str], Optional[str], Optional[int], Optional[int]]:
    """Возвращает (path, format, width, height), сохраняя изображение один раз."""
    if xref in saved:
        return saved[xref]
    path: Optional[str] = None
    fmt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    try:
        info = pdf.extract_image(xref) or {}
        fmt = info.get("ext")
        width = info.get("width")
        height = info.get("height")
        data = info.get("image")
        if image_dir is not None and data and fmt:
            ext = fmt if fmt in IMAGE_FORMATS else IMAGE_DEFAULT_EXTENSION
            path = os.path.join(image_dir, f"img_{xref}.{ext}")
            with open(path, "wb") as handle:
                handle.write(data)
    except Exception as exc:  # noqa: BLE001 — изображение не критично
        errors.append(f"Не удалось извлечь изображение (xref={xref}): {exc}")
    result = (path, fmt, width, height)
    saved[xref] = result
    return result


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
