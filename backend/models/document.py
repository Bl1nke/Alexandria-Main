"""Модели документа и его элементов.

Единое представление результата извлечения для PDF и DOCX. В DOCX нет
координат в том смысле, в котором они есть в PDF, поэтому все поля bbox
необязательные (``None`` означает «координаты недоступны», а не «нуль»).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional

from models.layout import Column, PageLayout
from models.validation import Confidence

# "pdf" | "docx"; набор поддерживаемых значений — в config/parser_settings.py
DocType = str


@dataclass
class BBox:
    """Прямоугольная область на странице (координаты в точках PDF)."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        """Ширина области."""
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        """Высота области."""
        return self.y1 - self.y0

    def to_dict(self) -> Dict[str, float]:
        """Сериализует область в словарь."""
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1}


@dataclass
class TextBlock:
    """Фрагмент текста из документа.

    Для PDF это блок текста с координатами; для DOCX — абзац, у которого
    координат нет (``bbox = None``). ``block_type`` различает абзацы,
    заголовки, элементы списков и подписи. ``extraction_index`` хранит
    порядок, в котором блок был извлечён из исходного документа (может
    отличаться от ``order`` — порядка чтения, который проставляет
    layout-анализ).
    """

    text: str
    page: int
    bbox: Optional[BBox] = None
    font_size: Optional[float] = None
    is_bold: bool = False
    order: Optional[int] = None
    id: str = ""
    block_type: str = "paragraph"
    level: Optional[int] = None
    font_name: Optional[str] = None
    is_italic: bool = False
    source: str = ""
    extraction_index: Optional[int] = None
    # Результаты анализа макета (Этап 3) — добавляются, не заменяя исходные поля.
    column: Optional[int] = None
    alignment: Optional[str] = None
    caption_for: Optional[str] = None
    origin_index: Optional[int] = None

    def to_dict(self) -> Dict[str, object]:
        """Сериализует блок в словарь."""
        return {
            "id": self.id,
            "text": self.text,
            "page": self.page,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "font_size": self.font_size,
            "font_name": self.font_name,
            "is_bold": self.is_bold,
            "is_italic": self.is_italic,
            "block_type": self.block_type,
            "level": self.level,
            "source": self.source,
            "order": self.order,
            "extraction_index": self.extraction_index,
            "column": self.column,
            "alignment": self.alignment,
            "caption_for": self.caption_for,
            "origin_index": self.origin_index,
        }


@dataclass
class ImageRef:
    """Ссылка на изображение документа.

    ``path`` указывает на сохранённый файл (если извлечение писалось на
    диск), ``format`` — исходный формат. ``data`` заполняется только когда
    изображение удерживается в памяти; для больших документов бинарные
    данные не хранятся (работа с изображениями ведётся последовательно).
    """

    id: str
    page: int
    bbox: Optional[BBox] = None
    mime: str = "image/png"
    data: Optional[bytes] = None
    path: Optional[str] = None
    format: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    # Результаты анализа макета (Этап 3).
    column: Optional[int] = None
    full_width: Optional[bool] = None
    caption_id: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        """Сериализует метаданные изображения (без бинарных данных)."""
        return {
            "id": self.id,
            "page": self.page,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "mime": self.mime,
            "format": self.format,
            "path": self.path,
            "width": self.width,
            "height": self.height,
            "has_data": self.data is not None,
            "column": self.column,
            "full_width": self.full_width,
            "caption_id": self.caption_id,
        }


@dataclass
class TableCell:
    """Ячейка таблицы с позицией в сетке и (по возможности) координатами."""

    row: int
    col: int
    text: str
    row_span: int = 1
    col_span: int = 1
    bbox: Optional[BBox] = None

    def to_dict(self) -> Dict[str, object]:
        """Сериализует ячейку в словарь."""
        return {
            "row": self.row,
            "col": self.col,
            "text": self.text,
            "row_span": self.row_span,
            "col_span": self.col_span,
            "bbox": self.bbox.to_dict() if self.bbox else None,
        }


@dataclass
class Table:
    """Таблица документа с сохранением структуры строк и столбцов.

    ``rows`` — список строк, каждая строка — список :class:`TableCell`.
    Для PDF ячейки могут иметь координаты, для DOCX — нет.
    """

    id: str
    page: int
    bbox: Optional[BBox] = None
    rows: List[List[TableCell]] = field(default_factory=list)
    order: Optional[int] = None
    source: str = ""
    # Результаты анализа макета (Этап 3).
    column: Optional[int] = None
    full_width: Optional[bool] = None
    caption_id: Optional[str] = None

    @property
    def n_rows(self) -> int:
        """Количество строк таблицы."""
        return len(self.rows)

    @property
    def n_cols(self) -> int:
        """Количество столбцов (по самой длинной строке)."""
        return max((len(row) for row in self.rows), default=0)

    def text(self) -> str:
        """Текст таблицы: строки, склеенные из ячеек через ``|``."""
        return "\n".join(" | ".join(cell.text for cell in row) for row in self.rows)

    def to_dict(self) -> Dict[str, object]:
        """Сериализует таблицу в словарь."""
        return {
            "id": self.id,
            "page": self.page,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "n_rows": self.n_rows,
            "n_cols": self.n_cols,
            "order": self.order,
            "source": self.source,
            "column": self.column,
            "full_width": self.full_width,
            "caption_id": self.caption_id,
            "rows": [[cell.to_dict() for cell in row] for row in self.rows],
        }


@dataclass
class Page:
    """Страница документа (для DOCX — логическая страница)."""

    number: int
    width: float
    height: float
    blocks: List[TextBlock] = field(default_factory=list)
    images: List[ImageRef] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    needs_ocr: bool = False
    # Результат анализа макета страницы (Этап 3).
    layout: Optional[PageLayout] = None

    @property
    def has_text(self) -> bool:
        """Есть ли на странице непустой текст."""
        return any(block.text.strip() for block in self.blocks)

    @property
    def has_images(self) -> bool:
        """Есть ли на странице изображения."""
        return bool(self.images)

    @property
    def block_count(self) -> int:
        """Количество текстовых блоков на странице."""
        return len(self.blocks)

    @property
    def column_count(self) -> Optional[int]:
        """Число колонок страницы (из анализа макета), либо ``None``."""
        return self.layout.column_count if self.layout else None

    def text(self) -> str:
        """Текст страницы, собранный из блоков в их текущем порядке."""
        return "\n".join(block.text for block in self.blocks)

    def to_dict(self) -> Dict[str, object]:
        """Сериализует страницу в словарь."""
        return {
            "number": self.number,
            "width": self.width,
            "height": self.height,
            "block_count": self.block_count,
            "has_images": self.has_images,
            "needs_ocr": self.needs_ocr,
            "layout": self.layout.to_dict() if self.layout else None,
            "blocks": [block.to_dict() for block in self.blocks],
            "images": [image.to_dict() for image in self.images],
            "tables": [table.to_dict() for table in self.tables],
        }


@dataclass
class Document:
    """Загруженный документ: страницы, метаданные, уверенность.

    ``warnings`` — нефатальные замечания извлечения (например, «страница
    требует OCR»), ``errors`` — сообщения об ошибках, которые удалось
    пережить (например, не удалось сохранить изображение на диск).
    """

    source_path: str
    doc_type: DocType
    pages: List[Page] = field(default_factory=list)
    metadata: Dict[str, object] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    confidence: Confidence = Confidence.HIGH

    @property
    def page_count(self) -> int:
        """Количество страниц."""
        return len(self.pages)

    def blocks(self) -> Iterator[TextBlock]:
        """Итератор по всем текстовым блокам всех страниц."""
        for page in self.pages:
            yield from page.blocks

    def tables(self) -> Iterator[Table]:
        """Итератор по всем таблицам всех страниц."""
        for page in self.pages:
            yield from page.tables

    def images(self) -> Iterator[ImageRef]:
        """Итератор по всем изображениям всех страниц."""
        for page in self.pages:
            yield from page.images

    def pages_needing_ocr(self) -> List[int]:
        """Номера страниц, отмеченных как требующие OCR."""
        return [page.number for page in self.pages if page.needs_ocr]

    def text(self) -> str:
        """Полный текст документа."""
        return "\n".join(page.text() for page in self.pages)

    def to_dict(self) -> Dict[str, object]:
        """Сериализует документ в словарь."""
        return {
            "source_path": self.source_path,
            "doc_type": self.doc_type,
            "page_count": self.page_count,
            "metadata": dict(self.metadata),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "pages_needing_ocr": self.pages_needing_ocr(),
            "confidence": self.confidence.value,
            "pages": [page.to_dict() for page in self.pages],
        }
