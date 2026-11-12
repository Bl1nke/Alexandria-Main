"""Обнаружение возможных заголовков заданий.

Этап 1: только интерфейс. Адаптивный алгоритм (регулярные выражения +
контекст + геометрия документа + анализ последовательности заданий)
реализуется на этапе 2. Любой найденный номер задания обязан проходить
проверку контекста.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from models.document import BBox, Document
from models.validation import Confidence


@dataclass
class TaskCandidate:
    """Возможный заголовок задания, найденный в документе."""

    number: int
    page: int
    bbox: Optional[BBox] = None
    text: str = ""
    confidence: Confidence = Confidence.LOW


def detect_task_candidates(document: Document) -> List[TaskCandidate]:
    """Возвращает список кандидатов-заголовков заданий.

    Raises:
        NotImplementedError: обнаружение заданий реализуется на этапе 2.
    """
    raise NotImplementedError("Обнаружение заданий реализуется на этапе 2")
