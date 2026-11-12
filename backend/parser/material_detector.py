"""Обнаружение общих материалов (текстов, таблиц, изображений).

Этап 1: только интерфейс. Поиск общих материалов варианта (например,
текста к заданиям 1–3 и к заданиям 23–26) реализуется на этапе 2.
"""

from __future__ import annotations

from typing import List

from models.document import Document
from models.material import Material


def detect_materials(document: Document) -> List[Material]:
    """Возвращает список общих материалов документа.

    Raises:
        NotImplementedError: поиск материалов реализуется на этапе 2.
    """
    raise NotImplementedError("Поиск общих материалов реализуется на этапе 2")
