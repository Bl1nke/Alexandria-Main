"""Определение границ и содержимого заданий.

Этап 1: только интерфейс. Разделение документа на задания (от начала
заголовка до следующего заголовка или строки ответа) реализуется на
этапе 2.
"""

from __future__ import annotations

from typing import List, Sequence

from models.document import Document
from models.task import Task
from parser.task_detector import TaskCandidate


def segment_tasks(document: Document, candidates: Sequence[TaskCandidate]) -> List[Task]:
    """Строит задания по найденным кандидатам-заголовкам.

    Raises:
        NotImplementedError: сегментация заданий реализуется на этапе 2.
    """
    raise NotImplementedError("Сегментация заданий реализуется на этапе 2")
