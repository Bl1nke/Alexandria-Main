"""Модель задания варианта ЕГЭ."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from models.document import BBox
from models.validation import Confidence


@dataclass
class Task:
    """Задание варианта: номер, тип, текст, связи и уверенность.

    Поле ``task_type`` хранит строковый ключ типа (например,
    ``union_selection``), совпадающий с ключами в scorer.py и
    config/ege_russian_tasks.py, чтобы оценивание не приходилось менять.
    """

    number: int
    display_id: str
    text: str = ""
    task_type: str = "unknown"
    answer_format: Optional[str] = None
    part: int = 1
    max_points: int = 1
    page: Optional[int] = None
    bbox: Optional[BBox] = None
    material_ids: List[str] = field(default_factory=list)
    image_ids: List[str] = field(default_factory=list)
    confidence: Confidence = Confidence.LOW
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        """Сериализует задание в словарь."""
        return {
            "number": self.number,
            "display_id": self.display_id,
            "text": self.text,
            "task_type": self.task_type,
            "answer_format": self.answer_format,
            "part": self.part,
            "max_points": self.max_points,
            "page": self.page,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "material_ids": list(self.material_ids),
            "image_ids": list(self.image_ids),
            "confidence": self.confidence.value,
            "warnings": list(self.warnings),
        }
