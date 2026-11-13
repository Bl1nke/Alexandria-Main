"""Общие фикстуры для тестов парсера.

Фикстуры PDF и DOCX генерируются программно средствами уже установленных
библиотек (PyMuPDF и python-docx), поэтому в репозиторий не попадают
сторонние бинарные файлы. Реальные образцы (если присутствуют в
backend/uploads) подключаются отдельными фикстурами и пропускаются, если
файлов нет.
"""

from __future__ import annotations

import os
import sys

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

UPLOADS_DIR = os.path.join(BACKEND_DIR, "uploads")


def _find_upload(filename: str):
    """Ищет файл с заданным именем во вложенных каталогах backend/uploads."""
    if not os.path.isdir(UPLOADS_DIR):
        return None
    for root, _dirs, files in os.walk(UPLOADS_DIR):
        if filename in files:
            return os.path.join(root, filename)
    return None


@pytest.fixture
def sample_pdf(tmp_path) -> str:
    """Небольшой PDF с нумерованными строками, похожими на задания."""
    import pymupdf as fitz  # PyMuPDF

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 в пунктах
    lines = [
        "(1)Some shared text for tasks.",
        "1. Choose the correct conjunction.",
        "1) option one",
        "ANSWER:",
        "2. Indicate the answer options.",
        "ANSWER:",
        "3. Read the text and complete the task.",
        "ANSWER:",
    ]
    y = 80
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 20
    path = tmp_path / "sample_variant.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def sample_docx(tmp_path) -> str:
    """Небольшой DOCX с абзацами и таблицей."""
    from docx import Document as DocxDocument

    document = DocxDocument()
    document.add_paragraph("(1)Some shared text for tasks.")
    document.add_paragraph("1. Choose the correct conjunction.")
    document.add_paragraph("2. Indicate the answer options.")

    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "word"
    table.cell(0, 1).text = "meaning"
    table.cell(1, 0).text = "alpha"
    table.cell(1, 1).text = "beta"

    path = tmp_path / "sample_variant.docx"
    document.save(str(path))
    return str(path)


@pytest.fixture
def answers_pdf(tmp_path) -> str:
    """PDF с простой таблицей ответов (с нарисованными границами)."""
    import pymupdf as fitz  # PyMuPDF

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    xs = [72.0, 200.0, 280.0, 400.0]
    ys = [72.0, 100.0, 128.0]
    for x in xs:
        page.draw_line(fitz.Point(x, ys[0]), fitz.Point(x, ys[-1]))
    for y in ys:
        page.draw_line(fitz.Point(xs[0], y), fitz.Point(xs[-1], y))

    cells = [
        ("№ п/п", "№", "ответ"),
        ("1", "1", "134"),
    ]
    for row_index, row in enumerate(cells):
        for col_index, value in enumerate(row):
            page.insert_text(
                (xs[col_index] + 4, ys[row_index] + 18),
                value,
                fontsize=11,
            )

    path = tmp_path / "answers.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def answers_docx(tmp_path) -> str:
    """DOCX с таблицей ответов."""
    from docx import Document as DocxDocument

    document = DocxDocument()
    table = document.add_table(rows=3, cols=3)
    header = ["№ п/п", "№ задания", "ответ"]
    for col_index, value in enumerate(header):
        table.cell(0, col_index).text = value
    table.cell(1, 0).text = "1"
    table.cell(1, 1).text = "1"
    table.cell(1, 2).text = "134"
    table.cell(2, 0).text = "2"
    table.cell(2, 1).text = "2"
    table.cell(2, 2).text = "word"

    path = tmp_path / "answers.docx"
    document.save(str(path))
    return str(path)


@pytest.fixture
def real_variant_pdf():
    """Реальный образец варианта из backend/uploads (если есть)."""
    path = _find_upload("variant.pdf")
    if not path:
        pytest.skip("Реальный образец variant.pdf отсутствует в backend/uploads")
    return path


@pytest.fixture
def real_answers_pdf():
    """Реальный образец ответов из backend/uploads (если есть)."""
    path = _find_upload("answers_raw.pdf")
    if not path:
        pytest.skip("Реальный образец answers_raw.pdf отсутствует в backend/uploads")
    return path

# ─── PDF: расширенные фикстуры (Этап 2) ──────────────────────


def _make_png_bytes(width: int = 60, height: int = 40, color=(200, 30, 30)) -> bytes:
    """Создаёт небольшое PNG-изображение в памяти."""
    import io

    from PIL import Image

    image = Image.new("RGB", (width, height), color)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def multipage_pdf(tmp_path) -> str:
    """PDF с несколькими страницами текста."""
    import pymupdf

    doc = pymupdf.open()
    for index in range(1, 4):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 80), f"Page {index} first line", fontsize=12)
        page.insert_text((72, 100), f"Page {index} second line", fontsize=12)
    path = tmp_path / "multipage.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def table_pdf(tmp_path) -> str:
    """PDF с таблицей, нарисованной рамками."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    xs = [72.0, 200.0, 280.0]
    ys = [72.0, 100.0, 128.0, 156.0]
    for x in xs:
        page.draw_line((x, ys[0]), (x, ys[-1]))
    for y in ys:
        page.draw_line((xs[0], y), (xs[-1], y))
    data = [["N", "answer"], ["1", "134"], ["2", "word"]]
    for row_index, row in enumerate(data):
        for col_index, value in enumerate(row):
            page.insert_text((xs[col_index] + 4, ys[row_index] + 18), value, fontsize=11)
    path = tmp_path / "table.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def image_pdf(tmp_path) -> str:
    """PDF с одним встроенным изображением (без текстового слоя)."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=300, height=300)
    page.insert_image(pymupdf.Rect(50, 50, 150, 120), stream=_make_png_bytes())
    path = tmp_path / "image.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def scanned_pdf(tmp_path) -> str:
    """PDF-«скан»: картинка на всю страницу и нет текстового слоя."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(
        pymupdf.Rect(0, 0, 595, 842), stream=_make_png_bytes(200, 280, (240, 240, 240))
    )
    path = tmp_path / "scanned.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def two_column_pdf(tmp_path) -> str:
    """PDF с двумя колонками текста (левая и правая)."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    for index in range(3):
        page.insert_text((60, 80 + index * 18), f"left column line {index}", fontsize=11)
        page.insert_text((330, 80 + index * 18), f"right column line {index}", fontsize=11)
    path = tmp_path / "two_column.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def corrupted_pdf(tmp_path) -> str:
    """«PDF» с корректной сигнатурой, но повреждённым содержимым."""
    path = tmp_path / "corrupted.pdf"
    path.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailing junk")
    return str(path)


# ─── DOCX: расширенные фикстуры (Этап 2) ─────────────────────


@pytest.fixture
def docx_with_image(tmp_path) -> str:
    """DOCX с абзацем и встроенным изображением."""
    import io

    from docx import Document as DocxDocument

    document = DocxDocument()
    document.add_paragraph("Paragraph before image")
    document.add_picture(io.BytesIO(_make_png_bytes()))
    document.add_paragraph("Paragraph after image")

    path = tmp_path / "with_image.docx"
    document.save(str(path))
    return str(path)


@pytest.fixture
def multipage_docx(tmp_path) -> str:
    """DOCX с явным разрывом страницы между двумя абзацами."""
    from docx import Document as DocxDocument

    document = DocxDocument()
    document.add_paragraph("First page content")
    document.add_page_break()
    document.add_paragraph("Second page content")

    path = tmp_path / "multipage.docx"
    document.save(str(path))
    return str(path)


@pytest.fixture
def styled_docx(tmp_path) -> str:
    """DOCX с заголовком, списком и жирным/курсивным текстом."""
    from docx import Document as DocxDocument

    document = DocxDocument()
    document.add_heading("Big Heading", level=1)
    document.add_paragraph("Bullet item", style="List Bullet")
    paragraph = document.add_paragraph()
    bold_run = paragraph.add_run("bold part")
    bold_run.bold = True
    italic_run = paragraph.add_run(" italic part")
    italic_run.italic = True

    path = tmp_path / "styled.docx"
    document.save(str(path))
    return str(path)


@pytest.fixture
def mixed_docx(tmp_path) -> str:
    """DOCX со смешанным содержимым: абзац, таблица, изображение."""
    import io

    from docx import Document as DocxDocument

    document = DocxDocument()
    document.add_paragraph("Intro paragraph")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "word"
    table.cell(0, 1).text = "meaning"
    table.cell(1, 0).text = "alpha"
    table.cell(1, 1).text = "beta"
    document.add_picture(io.BytesIO(_make_png_bytes()))
    document.add_paragraph("Outro paragraph")

    path = tmp_path / "mixed.docx"
    document.save(str(path))
    return str(path)


@pytest.fixture
def corrupted_docx(tmp_path) -> str:
    """«DOCX» с корректной ZIP-сигнатурой, но повреждённым содержимым."""
    path = tmp_path / "corrupted.docx"
    path.write_bytes(b"PK\x03\x04garbagegarbage")
    return str(path)


# ─── Макет: фикстуры (Этап 3) ────────────────────────────────


@pytest.fixture
def single_column_pdf(tmp_path) -> str:
    """Одноколоночная страница."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    for index in range(6):
        page.insert_text((72, 80 + index * 18), f"Single column body line number {index}", fontsize=11)
    path = tmp_path / "single_column.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def two_column_layout_pdf(tmp_path) -> str:
    """Две колонки с общими базовыми линиями."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    for index in range(4):
        page.insert_text((60, 80 + index * 18), f"Left column body line {index}", fontsize=11)
        page.insert_text((330, 80 + index * 18), f"Right column body line {index}", fontsize=11)
    path = tmp_path / "two_column_layout.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def three_column_pdf(tmp_path) -> str:
    """Три колонки."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    for index in range(4):
        for col, x in enumerate((40, 220, 400)):
            page.insert_text((x, 80 + index * 18), f"Col{col} line {index}", fontsize=11)
    path = tmp_path / "three_column.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def mixed_layout_pdf(tmp_path) -> str:
    """Смешанный макет: полноширинный заголовок и две колонки."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(
        (60, 60), "FULL WIDTH HEADING ACROSS THE TOP OF THE PAGE", fontsize=14, fontname="hebo"
    )
    for index in range(4):
        page.insert_text((60, 130 + index * 18), f"Left paragraph line {index}", fontsize=11)
        page.insert_text((330, 130 + index * 18), f"Right paragraph line {index}", fontsize=11)
    path = tmp_path / "mixed_layout.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def full_width_heading_pdf(tmp_path) -> str:
    """Полноширинный заголовок над одноколоночным текстом."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 70), "Centered Big Heading", fontsize=20, fontname="hebo")
    for index in range(5):
        page.insert_text((72, 110 + index * 18), f"Body paragraph line {index}", fontsize=11)
    path = tmp_path / "full_width_heading.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def table_between_text_pdf(tmp_path) -> str:
    """Таблица между двумя текстовыми блоками."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 70), "Text before the table here.", fontsize=11)
    xs = [72.0, 200.0, 280.0]
    ys = [110.0, 140.0, 170.0]
    for x in xs:
        page.draw_line((x, ys[0]), (x, ys[-1]))
    for y in ys:
        page.draw_line((xs[0], y), (xs[-1], y))
    for row_index, row in enumerate((("A", "B"), ("1", "2"))):
        for col_index, value in enumerate(row):
            page.insert_text((xs[col_index] + 4, ys[row_index] + 20), value, fontsize=11)
    page.insert_text((72, 220), "Text after the table here.", fontsize=11)
    path = tmp_path / "table_between.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def image_with_caption_pdf(tmp_path) -> str:
    """Изображение с подписью под ним."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 70), "Figure introduction paragraph.", fontsize=11)
    page.insert_image(pymupdf.Rect(72, 100, 260, 220), stream=_make_png_bytes(120, 80))
    page.insert_text((72, 240), "Рис. 1. Sample caption for the image", fontsize=10)
    path = tmp_path / "image_caption.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def typography_pdf(tmp_path) -> str:
    """Разные размеры и начертания шрифта, нумерованный список."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 70), "Document Title Heading", fontsize=20, fontname="hebo")
    page.insert_text((72, 110), "Regular paragraph sentence goes here.", fontsize=11)
    page.insert_text((72, 140), "1) first numbered item", fontsize=11)
    page.insert_text((72, 160), "2) second numbered item", fontsize=11)
    path = tmp_path / "typography.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def header_footer_pdf(tmp_path) -> str:
    """Несколько страниц с повторяющимся верхним и нижним колонтитулом."""
    import pymupdf

    doc = pymupdf.open()
    for index in range(3):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 20), "Running Header Text", fontsize=9)
        page.insert_text((72, 120 + index), f"Body content page line {index}", fontsize=11)
        page.insert_text((72, 820), "Page Footer Text", fontsize=9)
    path = tmp_path / "header_footer.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def continuation_pdf(tmp_path) -> str:
    """Абзац, продолжающийся на следующей странице."""
    import pymupdf

    doc = pymupdf.open()
    page1 = doc.new_page(width=595, height=842)
    page1.insert_text((72, 80), "This paragraph is cut off in the middle of the", fontsize=11)
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((72, 80), "sentence and continues here on the next page.", fontsize=11)
    path = tmp_path / "continuation.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


