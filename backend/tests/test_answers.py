"""Тесты извлечения ответов."""

from __future__ import annotations

from parser.answer_parser import parse_answers


def test_parse_answers_from_docx_table(answers_docx):
    answers = parse_answers(answers_docx)
    assert answers == {1: "134", 2: "word"}


def test_parse_answers_from_pdf_table(answers_pdf):
    answers = parse_answers(answers_pdf)
    assert answers.get(1) == "134"


def test_parse_answers_real_sample(real_answers_pdf):
    answers = parse_answers(real_answers_pdf)
    # Реальный образец: ожидаем ответы по номерам заданий.
    assert answers
    assert all(isinstance(number, int) for number in answers)
    assert all(isinstance(value, str) for value in answers.values())
