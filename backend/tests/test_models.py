"""Тесты моделей данных (Задача 3)."""

from __future__ import annotations

from models.document import BBox, Document, ImageRef, Page, TextBlock
from models.material import Material
from models.task import Task
from models.validation import Confidence, Severity, ValidationResult


def test_bbox_dimensions():
    bbox = BBox(x0=10, y0=20, x1=110, y1=70)
    assert bbox.width == 100
    assert bbox.height == 50
    assert bbox.to_dict() == {"x0": 10, "y0": 20, "x1": 110, "y1": 70}


def test_text_block_to_dict_with_and_without_bbox():
    block = TextBlock(text="hello", page=1, bbox=BBox(0, 0, 10, 10), font_size=12, is_bold=True)
    data = block.to_dict()
    assert data["text"] == "hello"
    assert data["bbox"] == {"x0": 0, "y0": 0, "x1": 10, "y1": 10}
    assert data["is_bold"] is True

    bare = TextBlock(text="x", page=2)
    assert bare.to_dict()["bbox"] is None


def test_page_and_document_text():
    page = Page(number=1, width=595, height=842)
    page.blocks = [TextBlock(text="first", page=1), TextBlock(text="second", page=1)]
    assert page.has_text is True
    assert page.text() == "first\nsecond"

    document = Document(source_path="a.pdf", doc_type="pdf", pages=[page])
    assert document.page_count == 1
    assert document.text() == "first\nsecond"
    assert [block.text for block in document.blocks()] == ["first", "second"]


def test_image_ref_serialization_hides_binary_data():
    image = ImageRef(id="img0", page=1, mime="image/png", data=b"\x00\x01")
    data = image.to_dict()
    assert data["has_data"] is True
    assert "data" not in data


def test_task_serialization():
    task = Task(
        number=8,
        display_id="8",
        text="Grammar task",
        task_type="grammar_error",
        answer_format="number_sequence",
        part=1,
        max_points=2,
        material_ids=["m1"],
        image_ids=["img0"],
        confidence=Confidence.MEDIUM,
    )
    data = task.to_dict()
    assert data["number"] == 8
    assert data["task_type"] == "grammar_error"
    assert data["max_points"] == 2
    assert data["material_ids"] == ["m1"]
    assert data["confidence"] == "medium"


def test_material_serialization():
    material = Material(id="t1", kind="text", text="shared text", page=1)
    data = material.to_dict()
    assert data["id"] == "t1"
    assert data["kind"] == "text"
    assert data["confidence"] == Confidence.LOW.value


def test_validation_result_collects_issues():
    result = ValidationResult()
    result.add("A", "warning", Severity.WARNING)
    result.add("B", "error", Severity.ERROR)
    assert len(result.warnings) == 1
    assert len(result.errors) == 1
    assert result.to_dict()["issues"][1]["severity"] == "error"
