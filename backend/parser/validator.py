"""Проверка корректности результата разбора.

Проверки структурные: наличие страниц и текста, корректность нумерации
заданий, отсутствие дублей и пропусков. Содержательные проверки
(правильность определённых типов заданий) появятся после этапа
обнаружения заданий.
"""

from __future__ import annotations

from typing import Optional, Sequence

from config.ege_russian_tasks import EXPECTED_TASK_NUMBERS
from models.document import Document
from models.task import Task
from models.validation import Confidence, Severity, ValidationResult


def validate(document: Document, tasks: Optional[Sequence[Task]] = None) -> ValidationResult:
    """Проверяет документ и, при наличии, список заданий.

    Args:
        document: загруженный документ.
        tasks: найденные задания (если уже обнаружены).

    Returns:
        :class:`ValidationResult` с набором проблем и итоговой уверенностью.
    """
    result = ValidationResult()

    _validate_document(document, result)
    if tasks is not None:
        _validate_tasks(tasks, result)

    result.is_valid = not result.errors
    result.confidence = _overall_confidence(document, result)
    return result


def _validate_document(document: Document, result: ValidationResult) -> None:
    if not document.pages:
        result.add("EMPTY_DOCUMENT", "Документ не содержит страниц", Severity.ERROR)
        return
    if not any(page.has_text for page in document.pages):
        result.add(
            "NO_TEXT",
            "Текст в документе не обнаружен (возможен скан)",
            Severity.WARNING,
        )


def _validate_tasks(tasks: Sequence[Task], result: ValidationResult) -> None:
    if not tasks:
        result.add("NO_TASKS", "Задания не обнаружены", Severity.WARNING)
        return

    numbers = [task.number for task in tasks]

    seen = set()
    for number in numbers:
        if number in seen:
            result.add(
                "DUPLICATE_TASK_NUMBER",
                f"Задание {number} встречается повторно",
                Severity.ERROR,
                task_number=number,
            )
        seen.add(number)

    if numbers != sorted(numbers):
        result.add(
            "TASKS_OUT_OF_ORDER",
            "Задания идут не по возрастанию номера",
            Severity.WARNING,
        )

    for number in numbers:
        if number not in EXPECTED_TASK_NUMBERS:
            result.add(
                "UNEXPECTED_TASK_NUMBER",
                f"Неожиданный номер задания: {number}",
                Severity.WARNING,
                task_number=number,
            )

    present = [n for n in EXPECTED_TASK_NUMBERS if n in seen]
    if present:
        first, last = present[0], present[-1]
        missing = [n for n in EXPECTED_TASK_NUMBERS if first <= n <= last and n not in seen]
        if missing:
            result.add(
                "TASK_NUMBER_GAP",
                f"Пропущены номера заданий: {missing}",
                Severity.WARNING,
            )

    for task in tasks:
        if not task.text.strip():
            result.add(
                "EMPTY_TASK_TEXT",
                f"Задание {task.number}: пустой текст",
                Severity.WARNING,
                task_number=task.number,
            )


def _overall_confidence(document: Document, result: ValidationResult) -> Confidence:
    """Итоговая уверенность: ошибки → LOW, предупреждения → не выше MEDIUM."""
    if result.errors:
        return Confidence.LOW
    if result.warnings and document.confidence is Confidence.HIGH:
        return Confidence.MEDIUM
    return document.confidence
