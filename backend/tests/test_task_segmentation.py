"""Тесты сегментации заданий (Этап 1: интерфейс-заглушка)."""

from __future__ import annotations

import pytest

from models.document import Document
from parser.task_segmenter import segment_tasks


def test_segment_tasks_raises_not_implemented():
    document = Document(source_path="x.pdf", doc_type="pdf")
    with pytest.raises(NotImplementedError):
        segment_tasks(document, [])
