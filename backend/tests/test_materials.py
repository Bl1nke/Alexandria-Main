"""Тесты поиска общих материалов (Этап 1: интерфейс-заглушка)."""

from __future__ import annotations

import pytest

from models.document import Document
from models.material import Material
from parser.material_detector import detect_materials


def test_material_defaults():
    material = Material(id="t1", kind="text", text="shared")
    assert material.confidence.value == "low"
    assert material.warnings == []


def test_detect_materials_raises_not_implemented():
    document = Document(source_path="x.pdf", doc_type="pdf")
    with pytest.raises(NotImplementedError):
        detect_materials(document)
