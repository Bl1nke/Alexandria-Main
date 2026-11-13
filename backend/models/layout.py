"""Модели результата анализа макета (Layout Analyzer).

Модуль не зависит от models.document, чтобы не создавать циклических
импортов: колонки и макет страницы описаны простыми числами и
идентификаторами элементов. Layout Analyzer заполняет эти структуры и
добавляет их к исходной модели документа, не удаляя данные извлечения.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from models.validation import Confidence

# "single" | "multi" | "mixed" | "unavailable" | "unknown"
LayoutType = str


@dataclass
class Column:
    """Колонка страницы: горизонтальные границы и входящие элементы."""

    index: int
    x0: float
    x1: float
    y0: Optional[float] = None
    y1: Optional[float] = None
    block_ids: List[str] = field(default_factory=list)
    confidence: Confidence = Confidence.LOW

    @property
    def width(self) -> float:
        """Ширина колонки."""
        return self.x1 - self.x0

    def to_dict(self) -> Dict[str, object]:
        """Сериализует колонку в словарь."""
        return {
            "index": self.index,
            "x0": self.x0,
            "x1": self.x1,
            "y0": self.y0,
            "y1": self.y1,
            "width": self.width,
            "block_ids": list(self.block_ids),
            "confidence": self.confidence.value,
        }


@dataclass
class PageLayout:
    """Результат анализа макета одной страницы."""

    page: int
    layout_type: LayoutType = "unknown"
    column_count: Optional[int] = None
    columns: List[Column] = field(default_factory=list)
    reading_order: List[str] = field(default_factory=list)
    confidence: Confidence = Confidence.LOW
    uncertain: bool = False
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        """Сериализует макет страницы в словарь."""
        return {
            "page": self.page,
            "layout_type": self.layout_type,
            "column_count": self.column_count,
            "columns": [column.to_dict() for column in self.columns],
            "reading_order": list(self.reading_order),
            "confidence": self.confidence.value,
            "uncertain": self.uncertain,
            "warnings": list(self.warnings),
        }
