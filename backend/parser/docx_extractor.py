"""Извлечение содержимого DOCX.

В DOCX нет координат и страниц в том смысле, в котором они есть в PDF,
поэтому весь документ представляется одной логической страницей, а у
текстовых блоков ``bbox = None``. Порядок блоков соответствует порядку
следования абзацев и таблиц в теле документа.
"""

from __future__ import annotations

from typing import Iterator, List, Tuple, Union

from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from models.document import Document, ImageRef, Page, TextBlock
from models.validation import Confidence

# 1 пункт = 12700 EMU (английских метрических единиц).
_EMU_PER_POINT = 12700.0


class DocxExtractor:
    """Экстрактор содержимого DOCX-файлов."""

    extensions = ("docx",)

    def extract(self, path: str) -> Document:
        """Извлекает абзацы, таблицы и изображения DOCX."""
        docx_document = DocxDocument(path)
        blocks: List[TextBlock] = []

        for element in _iter_body_elements(docx_document):
            if isinstance(element, Paragraph):
                text = element.text.strip()
                if text:
                    blocks.append(TextBlock(text=text, page=1))
            else:  # Table
                for row in element.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    row_text = " | ".join(cell for cell in cells if cell)
                    if row_text:
                        blocks.append(TextBlock(text=row_text, page=1))

        images = _extract_images(docx_document)
        width, height = _page_size_points(docx_document)
        page = Page(number=1, width=width, height=height, blocks=blocks, images=images)

        warnings: List[str] = []
        if not page.has_text:
            warnings.append("Текст в DOCX не обнаружен")

        return Document(
            source_path=path,
            doc_type="docx",
            pages=[page],
            metadata={"paragraphs": len(blocks)},
            warnings=warnings,
            confidence=Confidence.HIGH if page.has_text else Confidence.LOW,
        )


def _iter_body_elements(docx_document) -> Iterator[Union[Paragraph, Table]]:
    """Итерирует абзацы и таблицы тела документа в исходном порядке."""
    body = docx_document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, docx_document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, docx_document)


def _extract_images(docx_document) -> List[ImageRef]:
    """Собирает изображения документа по связям частей (relationships)."""
    images: List[ImageRef] = []
    seen = set()
    index = 0
    for rel in docx_document.part.rels.values():
        if "image" not in rel.reltype:
            continue
        part = rel.target_part
        partname = getattr(part, "partname", None)
        key = str(partname) if partname is not None else str(id(part))
        if key in seen:
            continue
        seen.add(key)
        images.append(
            ImageRef(
                id=f"img{index}",
                page=1,
                mime=getattr(part, "content_type", "image/png"),
                data=part.blob,
            )
        )
        index += 1
    return images


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
