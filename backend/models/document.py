"""Модели документа и его элементов.

Единое представление результата извлечения для PDF и DOCX. В DOCX нет
координат, поэтому все поля bbox необязательные.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional

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
    """Фрагмент текста из документа (строка PDF или абзац DOCX)."""

    text: str
    page: int
    bbox: Optional[BBox] = None
    font_size: Optional[float] = None
    is_bold: bool = False
    order: Optional[int] = None

    def to_dict(self) -> Dict[str, object]:
        """Сериализует блок в словарь."""
        return {
            "text": self.text,
            "page": self.page,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "font_size": self.font_size,
            "is_bold": self.is_bold,
            "order": self.order,
        }


@dataclass
class ImageRef:
    """Ссылка на изображение документа (данные могут загружаться лениво)."""

    id: str
    page: int
    bbox: Optional[BBox] = None
    mime: str = "image/png"
    data: Optional[bytes] = None

    def to_dict(self) -> Dict[str, object]:
        """Сериализует метаданные изображения (без бинарных данных)."""
        return {
            "id": self.id,
            "page": self.page,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "mime": self.mime,
            "has_data": self.data is not None,
        }


@dataclass
class Page:
    """Страница документа (для DOCX — одна логическая страница)."""

    number: int
    width: float
    height: float
    blocks: List[TextBlock] = field(default_factory=list)
    images: List[ImageRef] = field(default_factory=list)

    @property
    def has_text(self) -> bool:
        """Есть ли на странице непустой текст."""
        return any(block.text.strip() for block in self.blocks)

    def text(self) -> str:
        """Текст страницы, собранный из блоков в их текущем порядке."""
        return "\n".join(block.text for block in self.blocks)

    def to_dict(self) -> Dict[str, object]:
        """Сериализует страницу в словарь."""
        return {
            "number": self.number,
            "width": self.width,
            "height": self.height,
            "blocks": [block.to_dict() for block in self.blocks],
            "images": [image.to_dict() for image in self.images],
        }


@dataclass
class Document:
    """Загруженный документ: страницы, метаданные, уверенность."""

    source_path: str
    doc_type: DocType
    pages: List[Page] = field(default_factory=list)
    metadata: Dict[str, object] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    confidence: Confidence = Confidence.HIGH

    @property
    def page_count(self) -> int:
        """Количество страниц."""
        return len(self.pages)

    def blocks(self) -> Iterator[TextBlock]:
        """Итератор по всем текстовым блокам всех страниц."""
        for page in self.pages:
            yield from page.blocks

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
            "confidence": self.confidence.value,
            "pages": [page.to_dict() for page in self.pages],
        }
