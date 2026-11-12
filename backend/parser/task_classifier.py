"""Определение типа задания и формата ответа.

Этап 1: только интерфейс. Классификация по содержимому задания и
конфигурации ЕГЭ (config/ege_russian_tasks.py) реализуется на этапе 2.
"""

from __future__ import annotations

from typing import Optional

from config.ege_russian_tasks import TaskSpec


def classify_task(candidate_text: str, number: Optional[int] = None) -> TaskSpec:
    """Определяет тип задания по тексту-кандидату и (опционально) номеру.

    Raises:
        NotImplementedError: классификация заданий реализуется на этапе 2.
    """
    raise NotImplementedError("Классификация заданий реализуется на этапе 2")
