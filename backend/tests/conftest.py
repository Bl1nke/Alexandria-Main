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
