"""Тесты конфигурации заданий ЕГЭ по русскому языку (Задача 4)."""

from __future__ import annotations

import scorer

from config.ege_russian_tasks import (
    ESSAY_TASK_NUMBER,
    EXPECTED_TASK_NUMBERS,
    PART1_NUMBERS,
    TASK_SPECS,
    AnswerFormat,
    all_task_numbers,
    get_task_spec,
    task_type_key,
)
from config.parser_settings import confidence_level
from models.validation import Confidence


def test_all_task_numbers_are_1_to_27():
    assert EXPECTED_TASK_NUMBERS == tuple(range(1, 28))
    assert all_task_numbers() == tuple(range(1, 28))
    assert set(TASK_SPECS) == set(range(1, 28))


def test_spec_number_matches_key_and_part():
    for number, spec in TASK_SPECS.items():
        assert spec.number == number
        assert spec.part in (1, 2)
        assert spec.max_points >= 1
    assert set(PART1_NUMBERS) == set(range(1, 27))
    assert ESSAY_TASK_NUMBER == 27


def test_max_points_match_scorer():
    # Ключевые многобалльные задания и их значения совпадают со scorer.py.
    assert get_task_spec(8).max_points == scorer.TASK_MAX_POINTS[8] == 2
    assert get_task_spec(16).max_points == scorer.TASK_MAX_POINTS[16] == 2
    essay = get_task_spec(27)
    assert essay.max_points == scorer.TASK_MAX_POINTS[27] == 22
    assert essay.part == 2
    assert essay.answer_format is AnswerFormat.EXTENDED


def test_partial_rules():
    assert get_task_spec(8).partial_rule == "ordered"
    assert get_task_spec(16).partial_rule == "set"


def test_type_keys_are_stable_strings():
    assert task_type_key(1) == "union_selection"
    assert task_type_key(27) == "essay"
    assert task_type_key(999) == "unknown"


def test_unknown_number_returns_none():
    assert get_task_spec(0) is None
    assert get_task_spec(99) is None


def test_confidence_level_thresholds():
    assert confidence_level(1.0) is Confidence.HIGH
    assert confidence_level(0.6) is Confidence.MEDIUM
    assert confidence_level(0.1) is Confidence.LOW
