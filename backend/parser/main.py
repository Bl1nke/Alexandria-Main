"""Оркестратор обработки документа.

Задаёт последовательность этапов: загрузка → анализ расположения →
валидация. Обнаружение заданий, классификация, сегментация и поиск
материалов реализуются на этапе 2 (см. соответствующие модули-заглушки)
и на текущем этапе в конвейер не подключены.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from models.document import Document
from models.material import Material
from models.task import Task
from models.validation import ValidationResult
from parser.document_loader import load_document
from parser.layout_analyzer import analyze_layout
from parser.validator import validate


@dataclass
class ParseResult:
    """Результат обработки документа парсером."""

    document: Document
    tasks: List[Task] = field(default_factory=list)
    materials: List[Material] = field(default_factory=list)
    validation: Optional[ValidationResult] = None

    def to_dict(self) -> dict:
        """Сериализует результат в словарь."""
        return {
            "document": self.document.to_dict(),
            "tasks": [task.to_dict() for task in self.tasks],
            "materials": [material.to_dict() for material in self.materials],
            "validation": self.validation.to_dict() if self.validation else None,
        }


def parse_document(path: str, *, analyze: bool = True) -> ParseResult:
    """Загружает документ и выполняет базовые этапы обработки.

    Args:
        path: путь к PDF или DOCX файлу.
        analyze: выполнять ли анализ расположения блоков.

    Returns:
        :class:`ParseResult` с документом и результатом валидации.
        На этапе 1 списки ``tasks`` и ``materials`` пусты.
    """
    document = load_document(path)
    if analyze:
        analyze_layout(document)
    validation = validate(document, tasks=None)
    return ParseResult(document=document, tasks=[], materials=[], validation=validation)
