"""
МОДУЛЬ ПРОВЕРКИ ОТВЕТОВ ЕГЭ
"""

import re


def calculate_score(user_answers: dict, correct_answers: dict):
    """
    Проверяет ответы пользователя.

    Args:
        user_answers:    {"1": "ответ", ...}
        correct_answers: {"1": {"answer": "правильный", "type": "..."}, ...}

    Returns:
        (score, total, details)
    """
    score   = 0
    total   = len(correct_answers)
    details = []

    for task_id, task_data in correct_answers.items():
        user_ans    = str(user_answers.get(task_id, "")).strip()
        correct_ans = str(task_data.get("answer", "")).strip()
        task_type   = task_data.get("type", "unknown")

        is_correct = False

        if task_type == "essay":
            # Сочинение — минимальный объём
            is_correct = len(user_ans) >= 150
        elif task_type in ("orthography", "grammar", "punctuation",
                           "root_vowel", "prefix", "suffix",
                           "ne_with_word", "union_spelling", "nn_spelling"):
            is_correct = normalize(user_ans) == normalize(correct_ans)
        else:
            # Для остальных — нестрогое сравнение (без учёта регистра и пробелов)
            is_correct = normalize(user_ans) == normalize(correct_ans)

        if is_correct:
            score += 1

        details.append({
            "id":             task_id,
            "correct":        is_correct,
            "user_answer":    user_ans,
            "correct_answer": correct_ans,
            "type":           task_type,
        })

    return score, total, details


def normalize(s: str) -> str:
    """Нормализует строку для сравнения."""
    s = s.strip().lower()
    s = re.sub(r'\s+', ' ', s)
    # Убираем знаки препинания в конце
    s = s.rstrip('.,;:!?')
    return s