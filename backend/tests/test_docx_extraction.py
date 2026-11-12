"""Тесты извлечения содержимого DOCX (Этап 2).

Проверяется структура таблиц, метаданные изображений, разбиение на
логические страницы по разрывам, определение заголовков/списков/форматирования
и корректная обработка повреждённых файлов.
"""

from __future__ import annotations

import os

import pytest

from parser.document_loader import DocumentReadError, load_document


def test_paragraphs_have_no_coordinates(sample_docx):
    document = load_document(sample_docx)
    blocks = list(document.blocks())
    assert blocks
    for block in blocks:
        assert block.bbox is None
        assert block.source == "docx"


def test_table_structure_from_docx(mixed_docx):
    document = load_document(mixed_docx)
    tables = list(document.tables())
    assert len(tables) == 1
    table = tables[0]
    assert table.source == "docx"
    assert table.n_rows == 2
    assert table.n_cols == 2
    assert table.rows[0][0].text == "word"
    assert table.rows[1][1].text == "beta"
    # текст таблицы доступен и как часть полного текста документа
    assert "alpha" in document.text()


def test_images_saved_and_ordered(docx_with_image, tmp_path):
    target = tmp_path / "assets"
    document = load_document(docx_with_image, image_dir=str(target))
    images = list(document.images())
    assert len(images) == 1
    image = images[0]
    assert image.bbox is None  # координат в DOCX нет
    assert image.format == "png"
    assert image.width == 60 and image.height == 40
    assert image.path is not None and os.path.exists(image.path)
    # изображение расположено между абзацами и относится к странице
    page = document.pages[0]
    assert page.has_images
    assert image.page == 1


def test_page_breaks_split_logical_pages(multipage_docx):
    document = load_document(multipage_docx)
    assert document.page_count == 2
    assert "First page content" in document.pages[0].text()
    assert "Second page content" in document.pages[1].text()


def test_headings_lists_and_formatting(styled_docx):
    document = load_document(styled_docx)
    blocks = list(document.blocks())
    headings = [block for block in blocks if block.block_type == "heading"]
    assert headings
    assert headings[0].level == 1
    lists = [block for block in blocks if block.block_type == "list_item"]
    assert lists
    assert any(block.is_bold for block in blocks)
    assert any(block.is_italic for block in blocks)


def test_corrupted_docx_is_not_success(corrupted_docx):
    with pytest.raises(DocumentReadError):
        load_document(corrupted_docx)


def test_pdf_and_docx_produce_compatible_structure(table_pdf, mixed_docx):
    pdf_document = load_document(table_pdf)
    docx_document = load_document(mixed_docx)
    # одинаковый набор ключей верхнего уровня и у страниц
    assert set(pdf_document.to_dict()) == set(docx_document.to_dict())
    assert set(pdf_document.pages[0].to_dict()) == set(docx_document.pages[0].to_dict())
    # обе модели дают текстовые блоки, таблицы и изображения
    for document in (pdf_document, docx_document):
        assert list(document.blocks())
        assert list(document.tables())
        assert all(hasattr(page, "tables") for page in document.pages)
