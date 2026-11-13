"""Тесты анализа макета документа (Этап 3).

Проверяется фактическая правильность: число колонок, границы, порядок
блоков, классификация, связи подписи/переноса, а также совместимость PDF
и DOCX.
"""

from __future__ import annotations

from parser.document_loader import load_document
from parser.layout_analyzer import analyze_layout


def _ordered_texts(page):
    """Тексты блоков страницы в восстановленном порядке чтения."""
    by_id = {block.id: block for block in page.blocks}
    return [by_id[bid].text for bid in page.layout.reading_order if bid in by_id]


def test_single_column_layout(single_column_pdf):
    document = load_document(single_column_pdf)
    analyze_layout(document)
    page = document.pages[0]
    assert page.layout.layout_type == "single"
    assert page.layout.column_count == 1
    texts = _ordered_texts(page)
    assert texts[0].endswith("number 0")
    assert texts[-1].endswith("number 5")
    orders = [block.order for block in document.blocks()]
    assert orders == list(range(len(orders)))


def test_two_column_reading_order(two_column_layout_pdf):
    document = load_document(two_column_layout_pdf)
    analyze_layout(document)
    page = document.pages[0]
    assert page.layout.column_count == 2
    texts = _ordered_texts(page)
    assert len(texts) == 8
    # сначала вся левая колонка, затем правая
    assert all(text.startswith("Left") for text in texts[:4])
    assert all("Right" in text for text in texts[4:])
    left_x = [b.bbox.x0 for b in page.blocks if b.text.startswith("Left")]
    right_x = [b.bbox.x0 for b in page.blocks if "Right" in b.text]
    assert max(left_x) < min(right_x)
    assert all(b.column == 0 for b in page.blocks if b.text.startswith("Left"))
    assert all(b.column == 1 for b in page.blocks if "Right" in b.text)


def test_three_column_layout(three_column_pdf):
    document = load_document(three_column_pdf)
    analyze_layout(document)
    page = document.pages[0]
    assert page.layout.column_count == 3
    columns = page.layout.columns
    assert [column.index for column in columns] == [0, 1, 2]
    assert columns[0].x0 < columns[1].x0 < columns[2].x0
    texts = _ordered_texts(page)
    assert len(texts) == 12
    assert all(text.startswith("Col0") for text in texts[:4])
    assert all(text.startswith("Col1") for text in texts[4:8])
    assert all(text.startswith("Col2") for text in texts[8:])


def test_mixed_layout_full_width_heading(mixed_layout_pdf):
    document = load_document(mixed_layout_pdf)
    analyze_layout(document)
    page = document.pages[0]
    assert page.layout.column_count == 2
    assert page.layout.layout_type == "mixed"
    texts = _ordered_texts(page)
    assert texts[0].startswith("FULL WIDTH HEADING")


def test_full_width_heading_is_heading(full_width_heading_pdf):
    document = load_document(full_width_heading_pdf)
    analyze_layout(document)
    page = document.pages[0]
    headings = [b for b in page.blocks if b.block_type == "heading"]
    assert headings
    assert headings[0].text == "Centered Big Heading"
    assert page.layout.reading_order[0] == headings[0].id


def test_table_between_text_blocks(table_between_text_pdf):
    document = load_document(table_between_text_pdf)
    analyze_layout(document)
    page = document.pages[0]
    assert len(page.tables) == 1
    table = page.tables[0]
    assert table.full_width is not None
    order = page.layout.reading_order
    table_pos = order.index(table.id)
    before = [b for b in page.blocks if b.text.startswith("Text before")]
    after = [b for b in page.blocks if b.text.startswith("Text after")]
    assert before and after
    assert order.index(before[0].id) < table_pos < order.index(after[0].id)


def test_image_caption_linked(image_with_caption_pdf):
    document = load_document(image_with_caption_pdf)
    analyze_layout(document)
    page = document.pages[0]
    captions = [b for b in page.blocks if b.block_type == "caption"]
    assert captions
    assert page.images
    image = page.images[0]
    assert image.caption_id == captions[0].id
    assert captions[0].caption_for == image.id


def test_typography_classification(typography_pdf):
    document = load_document(typography_pdf)
    analyze_layout(document)
    page = document.pages[0]
    heading = [b for b in page.blocks if b.text == "Document Title Heading"]
    assert heading and heading[0].block_type == "heading"
    lists = [b for b in page.blocks if b.block_type == "list"]
    assert len(lists) == 2
    assert all(b.block_type != "heading" for b in lists)


def test_continuation_between_pages(continuation_pdf):
    document = load_document(continuation_pdf)
    analyze_layout(document)
    links = document.metadata.get("continuation_links")
    assert links
    assert len(links) == 1


def test_repeated_header_footer(header_footer_pdf):
    document = load_document(header_footer_pdf)
    analyze_layout(document)
    roles = set()
    for page in document.pages:
        for block in page.blocks:
            if block.block_type in ("header", "footer"):
                roles.add(block.block_type)
        header_footer_ids = {
            b.id for b in page.blocks if b.block_type in ("header", "footer")
        }
        assert not (header_footer_ids & set(page.layout.reading_order))
    assert roles == {"header", "footer"}


def test_docx_tables_and_lists(styled_docx, mixed_docx):
    styled = load_document(styled_docx)
    analyze_layout(styled)
    styled_page = styled.pages[0]
    assert styled_page.layout.layout_type == "unavailable"
    assert styled_page.layout.column_count is None
    assert any(b.block_type == "heading" for b in styled.blocks())
    assert any(b.block_type == "list" for b in styled.blocks())

    mixed = load_document(mixed_docx)
    analyze_layout(mixed)
    assert any(b.block_type == "table" for b in mixed.blocks())
    assert list(mixed.tables())


def test_docx_without_coordinates_is_structured(sample_docx):
    document = load_document(sample_docx)
    analyze_layout(document)
    page = document.pages[0]
    assert all(block.bbox is None for block in page.blocks)
    assert page.layout.layout_type == "unavailable"
    assert page.layout.uncertain is True
    assert page.layout.reading_order[: len(page.blocks)] == [b.id for b in page.blocks]


def test_reading_order_restored_despite_wrong_extraction(two_column_layout_pdf):
    document = load_document(two_column_layout_pdf)
    page = document.pages[0]
    page.blocks = list(reversed(page.blocks))
    for index, block in enumerate(page.blocks):
        block.extraction_index = index
    analyze_layout(document)
    texts = _ordered_texts(page)
    assert all(text.startswith("Left") for text in texts[:4])
    assert all("Right" in text for text in texts[4:])


def test_pdf_and_docx_layouts_are_compatible(single_column_pdf, sample_docx):
    pdf = load_document(single_column_pdf)
    analyze_layout(pdf)
    docx = load_document(sample_docx)
    analyze_layout(docx)
    assert set(pdf.pages[0].layout.to_dict()) == set(docx.pages[0].layout.to_dict())
    assert set(pdf.pages[0].to_dict()) == set(docx.pages[0].to_dict())
