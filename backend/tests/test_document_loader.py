"""Тесты загрузки документов (Задача 5)."""

from __future__ import annotations

import pytest

from models.validation import Confidence
from parser.document_loader import (
    UnsupportedFormatError,
    detect_doc_type,
    get_extractor,
    load_document,
)


def test_detect_pdf_type(sample_pdf):
    assert detect_doc_type(sample_pdf) == "pdf"


def test_detect_docx_type(sample_docx):
    assert detect_doc_type(sample_docx) == "docx"


def test_load_pdf_document(sample_pdf):
    document = load_document(sample_pdf)
    assert document.doc_type == "pdf"
    assert document.page_count >= 1
    assert document.pages[0].has_text is True
    # У PDF у блоков должны быть координаты.
    assert all(block.bbox is not None for block in document.blocks())


def test_load_docx_document(sample_docx):
    document = load_document(sample_docx)
    assert document.doc_type == "docx"
    assert document.page_count == 1
    assert document.pages[0].has_text is True
    # У DOCX координат нет.
    assert all(block.bbox is None for block in document.blocks())


def test_docx_table_extracted_as_text(sample_docx):
    document = load_document(sample_docx)
    text = document.text()
    assert "alpha" in text
    assert "beta" in text


def test_unsupported_format_raises(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("plain text", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError):
        detect_doc_type(str(path))


def test_missing_file_raises(tmp_path):
    with pytest.raises(UnsupportedFormatError):
        detect_doc_type(str(tmp_path / "missing.pdf"))


def test_signature_has_priority_over_extension(tmp_path):
    # Файл с расширением .docx, но PDF-содержимым должен распознаться как pdf.
    path = tmp_path / "mislabeled.docx"
    path.write_bytes(b"%PDF-1.4\n%%EOF")
    assert detect_doc_type(str(path)) == "pdf"


def test_get_extractor_returns_matching_extractor():
    assert "pdf" in get_extractor("pdf").extensions
    assert "docx" in get_extractor("docx").extensions
    with pytest.raises(UnsupportedFormatError):
        get_extractor("rtf")


def test_pdf_confidence_is_high_for_text_document(sample_pdf):
    document = load_document(sample_pdf)
    assert document.confidence is Confidence.HIGH
