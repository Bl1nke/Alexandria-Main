"""Тесты обнаружения заданий (Этап 1: интерфейс-заглушка)."""

from __future__ import annotations

import pytest

from models.validation import Confidence
from parser.document_loader import load_document
from parser.task_detector import TaskCandidate, detect_task_candidates


def test_task_candidate_defaults():
    candidate = TaskCandidate(number=1, page=1, text="1. Some task")
    assert candidate.number == 1
    assert candidate.page == 1
    assert candidate.bbox is None
    assert candidate.confidence is Confidence.LOW


def test_detect_task_candidates_raises_not_implemented(sample_pdf):
    document = load_document(sample_pdf)
    with pytest.raises(NotImplementedError):
        detect_task_candidates(document)
