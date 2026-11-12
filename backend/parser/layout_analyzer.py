"""Анализ расположения элементов и порядка чтения.

Базовая реализация: блоки сортируются по вертикальной координате, затем —
по горизонтальной, и получают сквозной номер порядка чтения. Если у
блоков нет координат (например, DOCX), сохраняется исходный порядок.

Это НЕ адаптивный анализ колонок — расширяется на этапе 2.
"""

from __future__ import annotations

from typing import List

from models.document import Document, Page, TextBlock


def analyze_layout(document: Document) -> Document:
    """Упорядочивает блоки документа и проставляет поле ``order``.

    Args:
        document: загруженный документ.

    Returns:
        Тот же документ с упорядоченными блоками (изменяется на месте).
    """
    counter = 0
    for page in document.pages:
        ordered = _sort_page_blocks(page)
        for block in ordered:
            block.order = counter
            counter += 1
        page.blocks = ordered
    return document


def _sort_page_blocks(page: Page) -> List[TextBlock]:
    """Возвращает блоки страницы в порядке чтения."""
    blocks = list(page.blocks)
    # Если хотя бы у одного блока нет координат, порядок считается
    # исходным (типичный случай DOCX).
    if any(block.bbox is None for block in blocks):
        return blocks
    return sorted(
        blocks,
        key=lambda block: (round(block.bbox.y0, 1), block.bbox.x0),
    )
