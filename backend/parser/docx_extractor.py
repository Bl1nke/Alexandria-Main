"""Извлечение содержимого DOCX.

Особенности формата DOCX (по сравнению с PDF):
  * координаты в том смысле, в котором они есть в PDF, недоступны — у
    текстовых блоков и изображений ``bbox = None`` (мы их не выдумываем);
  * реальных страниц в файле нет: разбиение на логические страницы
    выполняется только по явным разрывам (``w:br type="page"`` и
    ``w:lastRenderedPageBreak``), иначе документ считается одной страницей.

Порядок блоков соответствует порядку следования абзацев и таблиц в теле
документа. Извлекается не только ``document.paragraphs``: текст часто лежит
внутри таблиц, поэтому таблицы разбираются отдельно с сохранением
структуры строк и столбцов.
"""

from __future__ import annotations

import os
from typing import Dict, Iterator, List, Optional, Tuple, Union

from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph

from config.parser_settings import IMAGE_DEFAULT_EXTENSION, IMAGE_FORMATS
from models.document import Document, ImageRef, Page, Table, TableCell, TextBlock
from models.validation import Confidence
from parser.document_loader import DocumentReadError

# 1 пункт = 12700 EMU (английских метрических единиц).
_EMU_PER_POINT = 12700.0


class DocxExtractor:
    """Экстрактор содержимого DOCX-файлов."""

    extensions = ("docx",)

    def extract(self, path: str, *, image_dir: Optional[str] = None) -> Document:
        """Извлекает абзацы, таблицы и изображения DOCX.

        Args:
            path: путь к DOCX-файлу.
            image_dir: каталог для сохранения встроенных изображений. Если
                ``None``, изображения не записываются (формат и размер в
                пикселях всё равно определяются).

        Raises:
            DocumentReadError: файл не открывается или повреждён.
        """
        try:
            docx_document = DocxDocument(path)
        except Exception as exc:  # noqa: BLE001
            raise DocumentReadError(
                f"Не удалось открыть DOCX «{os.path.basename(path)}»: {exc}"
            ) from exc

        if image_dir is not None:
            os.makedirs(image_dir, exist_ok=True)

        errors: List[str] = []
        warnings: List[str] = []
        saved: Dict[str, Tuple] = {}
        pages: List[Page] = []
        width, height = _page_size_points(docx_document)

        blocks: List[TextBlock] = []
        images: List[ImageRef] = []
        tables: List[Table] = []
        block_index = 0
        image_index = 0
        table_index = 0
        page_no = 1

        for element in _iter_body_elements(docx_document):
            image_element = None
            breaks = 0
            if isinstance(element, Paragraph):
                text = element.text.strip()
                if text:
                    block_type, level = _classify_paragraph(element)
                    is_bold, is_italic, font_name, font_size = _paragraph_formatting(element)
                    blocks.append(
                        TextBlock(
                            text=text,
                            page=page_no,
                            font_size=font_size,
                            font_name=font_name,
                            is_bold=is_bold,
                            is_italic=is_italic,
                            id=f"p{page_no}_b{block_index}",
                            block_type=block_type,
                            level=level,
                            source="docx",
                            extraction_index=block_index,
                        )
                    )
                    block_index += 1
                image_element = element._p
                breaks = _count_page_breaks(element)
            else:  # Table
                tables.append(_build_table(element, f"tbl{table_index}", page_no))
                table_index += 1
                for row in element.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    row_text = " | ".join(cell for cell in cells if cell)
                    if row_text:
                        blocks.append(
                            TextBlock(
                                text=row_text,
                                page=page_no,
                                id=f"p{page_no}_b{block_index}",
                                block_type="table_row",
                                source="docx",
                                extraction_index=block_index,
                            )
                        )
                        block_index += 1
                image_element = element._tbl

            if image_element is not None:
                for spec in _element_image_specs(
                    image_element, docx_document, image_dir, saved, errors
                ):
                    images.append(
                        ImageRef(
                            id=f"p{page_no}_img{image_index}",
                            page=page_no,
                            path=spec["path"],
                            format=spec["format"],
                            mime=spec["mime"],
                            width=spec["width"],
                            height=spec["height"],
                        )
                    )
                    image_index += 1

            if breaks:
                pages.append(
                    Page(
                        number=page_no,
                        width=width,
                        height=height,
                        blocks=blocks,
                        images=images,
                        tables=tables,
                    )
                )
                blocks, images, tables = [], [], []
                page_no += breaks

        pages.append(
            Page(
                number=page_no,
                width=width,
                height=height,
                blocks=blocks,
                images=images,
                tables=tables,
            )
        )

        has_text = any(page.has_text for page in pages) or any(
            table.n_rows for page in pages for table in page.tables
        )
        if not has_text:
            warnings.append("Текст в DOCX не обнаружен")

        return Document(
            source_path=path,
            doc_type="docx",
            pages=pages,
            metadata={
                "page_count": len(pages),
                "blocks": block_index,
                "tables": table_index,
                "images": image_index,
                "image_dir": image_dir,
            },
            warnings=warnings,
            errors=errors,
            confidence=Confidence.HIGH if has_text else Confidence.LOW,
        )


def _iter_body_elements(docx_document) -> Iterator[Union[Paragraph, DocxTable]]:
    """Итерирует абзацы и таблицы тела документа в исходном порядке."""
    body = docx_document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, docx_document)
        elif child.tag == qn("w:tbl"):
            yield DocxTable(child, docx_document)


def _classify_paragraph(paragraph: Paragraph) -> Tuple[str, Optional[int]]:
    """Определяет тип абзаца: заголовок, элемент списка или обычный."""
    style_name = ""
    try:
        style_name = paragraph.style.name or ""
    except Exception:  # noqa: BLE001 — стиль может отсутствовать
        style_name = ""
    lowered = style_name.lower()
    if lowered.startswith("heading") or lowered.startswith("заголовок"):
        return "heading", _trailing_int(style_name)
    if lowered in ("title", "subtitle") or "название" in lowered:
        return "heading", 1
    if any(True for _ in paragraph._p.iter(qn("w:numPr"))):
        return "list_item", None
    if lowered.startswith("list") or "список" in lowered:
        return "list_item", None
    return "paragraph", None


def _trailing_int(text: str) -> Optional[int]:
    """Возвращает число в конце строки (например, «Heading 2» → 2)."""
    digits = ""
    for char in reversed(text):
        if char.isdigit():
            digits = char + digits
        else:
            break
    return int(digits) if digits else None


def _paragraph_formatting(
    paragraph: Paragraph,
) -> Tuple[bool, bool, Optional[str], Optional[float]]:
    """Возвращает (жирный, курсив, имя шрифта, размер шрифта) абзаца."""
    is_bold = False
    is_italic = False
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    for run in paragraph.runs:
        if run.bold:
            is_bold = True
        if run.italic:
            is_italic = True
        font = run.font
        if font_name is None and font is not None and font.name:
            font_name = font.name
        if font_size is None and font is not None and font.size is not None:
            font_size = font.size.pt
    return is_bold, is_italic, font_name, font_size


def _count_page_breaks(paragraph: Paragraph) -> int:
    """Считает разрывы страниц в абзаце (явные и «rendered»)."""
    count = 0
    for br in paragraph._p.iter(qn("w:br")):
        if br.get(qn("w:type")) == "page":
            count += 1
    count += sum(1 for _ in paragraph._p.iter(qn("w:lastRenderedPageBreak")))
    return count


def _grid_span(wtc) -> int:
    """Горизонтальное объединение ячейки (``w:gridSpan``)."""
    tc_pr = next((child for child in wtc if child.tag == qn("w:tcPr")), None)
    if tc_pr is None:
        return 1
    grid_span = next((child for child in tc_pr if child.tag == qn("w:gridSpan")), None)
    if grid_span is None:
        return 1
    value = grid_span.get(qn("w:val"))
    return int(value) if value and value.isdigit() else 1


def _vmerge_state(wtc) -> Optional[str]:
    """Состояние вертикального объединения ячейки (``w:vMerge``)."""
    tc_pr = next((child for child in wtc if child.tag == qn("w:tcPr")), None)
    if tc_pr is None:
        return None
    vmerge = next((child for child in tc_pr if child.tag == qn("w:vMerge")), None)
    if vmerge is None:
        return None
    return "restart" if vmerge.get(qn("w:val")) == "restart" else "continue"


def _cell_text(wtc) -> str:
    """Текст ячейки таблицы (по абзацам)."""
    lines: List[str] = []
    for paragraph in [child for child in wtc if child.tag == qn("w:p")]:
        text = "".join(node.text or "" for node in paragraph.iter(qn("w:t"))).strip()
        if text:
            lines.append(text)
    if not lines:  # возможно, в ячейке вложенная таблица
        text = "".join(node.text or "" for node in wtc.iter(qn("w:t"))).strip()
        if text:
            lines.append(text)
    return "\n".join(lines).strip()


def _build_table(docx_table: DocxTable, table_id: str, page_number: int) -> Table:
    """Строит :class:`Table` из таблицы DOCX с учётом объединённых ячеек."""
    rows_meta = [child for child in docx_table._tbl if child.tag == qn("w:tr")]
    grid: List[List[dict]] = []
    for r, wtr in enumerate(rows_meta):
        row: List[dict] = []
        col = 0
        for wtc in [child for child in wtr if child.tag == qn("w:tc")]:
            col_span = _grid_span(wtc)
            row.append(
                {
                    "row": r,
                    "col": col,
                    "text": _cell_text(wtc),
                    "col_span": col_span,
                    "vmerge": _vmerge_state(wtc),
                    "row_span": 1,
                }
            )
            col += col_span
        grid.append(row)

    # Расчёт row_span для вертикально объединённых ячеек.
    for r, row in enumerate(grid):
        for cell in row:
            if cell["vmerge"] == "restart":
                span = 1
                for below_row in grid[r + 1:]:
                    below = next((c for c in below_row if c["col"] == cell["col"]), None)
                    if below is not None and below["vmerge"] == "continue":
                        span += 1
                    else:
                        break
                cell["row_span"] = span

    rows: List[List[TableCell]] = []
    for row in grid:
        rows.append(
            [
                TableCell(
                    row=cell["row"],
                    col=cell["col"],
                    text=cell["text"],
                    row_span=cell["row_span"],
                    col_span=cell["col_span"],
                )
                for cell in row
                if cell["vmerge"] != "continue"
            ]
        )
    return Table(id=table_id, page=page_number, rows=rows, source="docx")


def _element_image_specs(xml_element, docx_document, image_dir, saved, errors) -> List[dict]:
    """Собирает описания изображений, найденных в элементе тела документа."""
    specs: List[dict] = []
    for drawing in xml_element.iter(qn("w:drawing")):
        blips = [b for b in drawing.iter(qn("a:blip")) if b.get(qn("r:embed"))]
        if not blips:
            continue
        embed = blips[0].get(qn("r:embed"))
        path, fmt, mime, width, height = _resolve_docx_image(
            docx_document, embed, image_dir, saved, errors
        )
        specs.append(
            {"path": path, "format": fmt, "mime": mime, "width": width, "height": height}
        )
    return specs


def _resolve_docx_image(docx_document, embed, image_dir, saved, errors) -> Tuple:
    """Возвращает (path, format, mime, width, height), сохраняя файл один раз."""
    if embed in saved:
        return saved[embed]
    path: Optional[str] = None
    fmt: Optional[str] = None
    mime = "image/png"
    width: Optional[int] = None
    height: Optional[int] = None
    try:
        rel = docx_document.part.rels[embed]
        part = rel.target_part
        blob = part.blob
        mime = getattr(part, "content_type", mime) or mime
        image = getattr(part, "image", None)
        if image is not None:
            fmt = getattr(image, "ext", None)
            width = getattr(image, "px_width", None)
            height = getattr(image, "px_height", None)
        if fmt is None:
            fmt = mime.split("/")[-1] if "/" in mime else IMAGE_DEFAULT_EXTENSION
        if image_dir is not None and blob:
            ext = fmt if fmt in IMAGE_FORMATS else IMAGE_DEFAULT_EXTENSION
            safe_name = embed.replace("/", "_")
            path = os.path.join(image_dir, f"{safe_name}.{ext}")
            with open(path, "wb") as handle:
                handle.write(blob)
    except Exception as exc:  # noqa: BLE001 — изображение не критично
        errors.append(f"Не удалось извлечь изображение DOCX ({embed}): {exc}")
    result = (path, fmt, mime, width, height)
    saved[embed] = result
    return result


def _page_size_points(docx_document) -> Tuple[float, float]:
    """Возвращает размер первой страницы в пунктах (или 0,0, если неизвестен)."""
    try:
        section = docx_document.sections[0]
        return (
            float(section.page_width) / _EMU_PER_POINT,
            float(section.page_height) / _EMU_PER_POINT,
        )
    except (IndexError, AttributeError, TypeError):
        return 0.0, 0.0
