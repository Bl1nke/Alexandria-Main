"""Извлечение правильных ответов из PDF и DOCX.

Возвращает простой словарь ``{номер задания: ответ}``. Построение полной
структуры ``answers.json`` (с типом, баллами и правилом частичного балла) —
задача будущего адаптера к серверу, а не этого модуля.

Алгоритм повторяет проверенную логику legacy-парсера: сначала пробуем
таблицы, затем — текстовое представление.
"""

from __future__ import annotations

import re
from typing import Dict, List

import pdfplumber
from docx import Document as DocxDocument

from parser.document_loader import detect_doc_type

_SKIP_TOKENS = {"№ п/п", "№ задания", "ответ", "answer", "решение:", "источник:"}
_NUMBER_RE = re.compile(r"^\d{1,2}$")


def parse_answers(path: str) -> Dict[int, str]:
    """Извлекает ответы из файла PDF или DOCX.

    Args:
        path: путь к файлу с ответами.

    Returns:
        Словарь ``{номер задания: ответ}``. Пустой словарь, если ответы
        не найдены.
    """
    doc_type = detect_doc_type(path)
    if doc_type == "docx":
        return _parse_docx(path)
    return _parse_pdf(path)


def _parse_pdf(path: str) -> Dict[int, str]:
    answers: Dict[int, str] = {}
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                _parse_table_rows(table, answers)
    if not answers:
        answers = _parse_pdf_text(path)
    return answers


def _parse_table_rows(table: List[List[str]], answers: Dict[int, str]) -> None:
    """Разбирает строки таблицы ответов, добавляя найденное в ``answers``."""
    for row in table:
        if not row or len(row) < 2:
            continue
        cells = [(cell or "").strip() for cell in row]
        number = cells[0]
        answer = cells[-1] if len(cells) >= 3 else cells[1]
        if not number or not answer:
            continue
        if number.lower() in _SKIP_TOKENS or answer.lower() in _SKIP_TOKENS:
            continue
        if _NUMBER_RE.match(number):
            answers[int(number)] = answer


def _parse_pdf_text(path: str) -> Dict[int, str]:
    """Запасной разбор ответов из текста PDF, если таблиц не нашлось."""
    answers: Dict[int, str] = {}
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for raw_line in (page.extract_text() or "").splitlines():
                line = raw_line.strip()
                match = re.match(r"^(\d{1,2})\s+\d{4,}\s+(.+)$", line)
                if match:
                    answers.setdefault(int(match.group(1)), match.group(2).strip())
                    continue
                match = re.match(r"^(\d{1,2})\s{2,}(.+)$", line)
                if match:
                    value = match.group(2).strip()
                    if value.lower() not in ("ответ", "answer"):
                        answers.setdefault(int(match.group(1)), value)
    return answers


def _parse_docx(path: str) -> Dict[int, str]:
    """Извлекает ответы из таблиц DOCX."""
    docx_document = DocxDocument(path)
    answers: Dict[int, str] = {}
    for table in docx_document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if len(cells) >= 2 and _NUMBER_RE.match(cells[0]):
                answers[int(cells[0])] = cells[-1]
    return answers
