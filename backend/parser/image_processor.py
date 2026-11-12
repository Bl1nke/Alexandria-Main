"""Обработка изображений: вырезание областей и связывание с заданиями.

Этап 1: только интерфейс. Рендеринг областей страницы в изображения и
связывание их с заданиями реализуется на этапе 2. Тяжёлые операции
(рендер, сжатие) должны выполняться по необходимости.
"""

from __future__ import annotations

from models.document import BBox, Document


def render_region(document: Document, page_number: int, bbox: BBox) -> bytes:
    """Рендерит область страницы документа в PNG-изображение.

    Raises:
        NotImplementedError: обработка изображений реализуется на этапе 2.
    """
    raise NotImplementedError("Обработка изображений реализуется на этапе 2")
