"""Модель общего материала (текста, таблицы или изображения)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from models.document import BBox
from models.validation import Confidence

# "text" | "table" | "image"
MaterialKind = str


@dataclass
class Material:
    """Общий материал, используемый одним или несколькими заданиями.

    Например, общий текст к заданиям 1–3 или к заданиям 23–26.
    """

    id: str
    kind: MaterialKind
    text: str = ""
    page: Optional[int] = None
    bbox: Optional[BBox] = None
    confidence: Confidence = Confidence.LOW
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        """Сериализует материал в словарь."""
        return {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "page": self.page,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "confidence": self.confidence.value,
            "warnings": list(self.warnings),
        }
