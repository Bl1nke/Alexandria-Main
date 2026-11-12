"""Тесты классификации заданий (Этап 1: интерфейс-заглушка)."""

from __future__ import annotations

import pytest

from parser.task_classifier import classify_task


def test_classify_task_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        classify_task("1. Choose the correct conjunction.", 1)


def test_classify_task_without_number_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        classify_task("Some task text")
