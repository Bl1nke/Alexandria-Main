"""Интеграционный тест взаимодействия модулей парсера."""

from __future__ import annotations

from parser import parse_document


def test_parse_document_returns_document_and_validation(sample_pdf):
    result = parse_document(sample_pdf)
    assert result.document.doc_type == "pdf"
    assert result.tasks == []
    assert result.materials == []
    assert result.validation is not None
    assert result.validation.is_valid


def test_parse_document_assigns_reading_order(sample_pdf):
    result = parse_document(sample_pdf)
    orders = [block.order for block in result.document.blocks()]
    assert orders == list(range(len(orders)))


def test_parse_document_to_dict(sample_pdf):
    result = parse_document(sample_pdf)
    data = result.to_dict()
    assert data["document"]["doc_type"] == "pdf"
    assert isinstance(data["tasks"], list)
    assert data["validation"] is not None
