"""Тесты извлечения содержимого PDF (Этап 2).

Проверяется не только факт возврата объекта, но и содержимое: координаты,
признаки шрифта, структура таблиц, метаданные изображений, детект сканов и
корректность обработки повреждённых файлов.
"""

from __future__ import annotations

import os

import pytest

from parser.document_loader import DocumentReadError, load_document


def test_text_blocks_have_coordinates_and_metadata(sample_pdf):
    document = load_document(sample_pdf)
    blocks = list(document.blocks())
    assert blocks
    for block in blocks:
        assert block.text.strip()
        assert block.bbox is not None
        assert block.source == "pdf"
        assert block.extraction_index is not None
    first = blocks[0]
    assert first.font_size and first.font_size > 0
    assert first.id.startswith("p1_b")


def test_multipage_pdf_pages(multipage_pdf):
    document = load_document(multipage_pdf)
    assert document.page_count == 3
    assert [page.number for page in document.pages] == [1, 2, 3]
    for page in document.pages:
        assert page.has_text
        assert page.block_count >= 2
        assert page.width > 0 and page.height > 0


def test_table_structure_extracted(table_pdf):
    document = load_document(table_pdf)
    tables = list(document.tables())
    assert len(tables) == 1
    table = tables[0]
    assert table.source == "pdf"
    assert table.n_rows == 3
    assert table.n_cols == 2
    assert table.rows[0][0].text == "N"
    assert table.rows[1][1].text == "134"
    assert table.rows[2][1].text == "word"
    # у ячеек и таблицы есть координаты (структура сохранена, не «плоский текст»)
    assert table.bbox is not None
    assert table.rows[1][1].bbox is not None


def test_images_metadata_without_saving(image_pdf):
    document = load_document(image_pdf)
    images = list(document.images())
    assert len(images) >= 1
    image = images[0]
    assert image.format == "png"
    assert image.width == 60 and image.height == 40
    assert image.bbox is not None
    # без image_dir файл на диск не пишется
    assert image.path is None


def test_images_saved_to_disk(image_pdf, tmp_path):
    target = tmp_path / "assets"
    document = load_document(image_pdf, image_dir=str(target))
    images = list(document.images())
    assert images
    image = images[0]
    assert image.path is not None
    assert os.path.exists(image.path)
    assert image.path.endswith(".png")
    assert os.path.getsize(image.path) > 0


def test_two_column_coordinates_preserved(two_column_pdf):
    document = load_document(two_column_pdf)
    page = document.pages[0]
    blocks = [block for block in page.blocks if block.bbox is not None]
    assert blocks
    text = document.text()
    assert "left column line 0" in text
    assert "right column line 0" in text
    # координаты сохранены как есть (исходные, без адаптивной пересортировки)
    assert all(0 <= block.bbox.x0 and block.bbox.x1 <= page.width for block in blocks)
    # правая колонка попадает в границы блоков (координаты не «схлопнуты»)
    assert any(block.bbox.x1 > 300 for block in blocks)
    # порядок извлечения сохранён без адаптивной пересортировки колонок
    indexes = [block.extraction_index for block in page.blocks]
    assert indexes == list(range(len(indexes)))


def test_scanned_pdf_flagged_for_ocr(scanned_pdf):
    document = load_document(scanned_pdf)
    page = document.pages[0]
    assert page.needs_ocr is True
    assert page.has_images is True
    assert 1 in document.pages_needing_ocr()
    assert any("OCR" in warning for warning in document.warnings)


def test_corrupted_pdf_is_not_success(corrupted_pdf):
    with pytest.raises(DocumentReadError):
        load_document(corrupted_pdf)


def test_document_serialization_has_new_fields(table_pdf):
    document = load_document(table_pdf)
    data = document.to_dict()
    assert "errors" in data
    assert "pages_needing_ocr" in data
    page = data["pages"][0]
    assert "tables" in page
    assert "needs_ocr" in page
    assert page["tables"][0]["n_rows"] == 3
