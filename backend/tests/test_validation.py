"""Тесты валидации результата разбора."""

from __future__ import annotations

from models.document import Document
from models.task import Task
from models.validation import Confidence
from parser.document_loader import load_document
from parser.validator import validate


def test_valid_document_has_no_errors(sample_pdf):
    document = load_document(sample_pdf)
    result = validate(document)
    assert result.is_valid
    assert result.errors == []


def test_empty_document_is_error():
    result = validate(Document(source_path="x.pdf", doc_type="pdf"))
    assert not result.is_valid
    assert result.confidence is Confidence.LOW
    assert any(issue.code == "EMPTY_DOCUMENT" for issue in result.errors)


def test_task_gap_produces_warning(sample_pdf):
    document = load_document(sample_pdf)
    tasks = [Task(number=1, display_id="1", text="a"), Task(number=3, display_id="3", text="b")]
    result = validate(document, tasks)
    assert any(issue.code == "TASK_NUMBER_GAP" for issue in result.warnings)
    assert result.is_valid  # пропуск — предупреждение, а не ошибка


def test_duplicate_task_produces_error(sample_pdf):
    document = load_document(sample_pdf)
    tasks = [Task(number=1, display_id="1", text="a"), Task(number=1, display_id="1b", text="b")]
    result = validate(document, tasks)
    assert any(issue.code == "DUPLICATE_TASK_NUMBER" for issue in result.errors)
    assert not result.is_valid


def test_unexpected_task_number_warning(sample_pdf):
    document = load_document(sample_pdf)
    tasks = [Task(number=99, display_id="99", text="a")]
    result = validate(document, tasks)
    assert any(issue.code == "UNEXPECTED_TASK_NUMBER" for issue in result.warnings)


def test_empty_task_text_warning(sample_pdf):
    document = load_document(sample_pdf)
    tasks = [Task(number=1, display_id="1", text="   ")]
    result = validate(document, tasks)
    assert any(issue.code == "EMPTY_TASK_TEXT" for issue in result.warnings)


def test_out_of_order_tasks_warning(sample_pdf):
    document = load_document(sample_pdf)
    tasks = [Task(number=2, display_id="2", text="a"), Task(number=1, display_id="1", text="b")]
    result = validate(document, tasks)
    assert any(issue.code == "TASKS_OUT_OF_ORDER" for issue in result.warnings)
