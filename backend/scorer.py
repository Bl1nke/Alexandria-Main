"""
МОДУЛЬ ПРОВЕРКИ ОТВЕТОВ ЕГЭ
Поддерживает варианты ответов через "или":
  "потомучто или таккак или оттогочто"
  "подпокровомночи или досихпор"
"""

import re


def normalize(s: str) -> str:
    """Нормализует строку: нижний регистр, убирает пробелы и знаки препинания."""
    s = s.strip().lower()
    s = re.sub(r'\s+', '', s)          # убираем все пробелы
    s = s.rstrip('.,;:!?')
    return s


def calculate_score(user_answers: dict, correct_answers: dict):
    """
    Проверяет ответы пользователя.

    Args:
        user_answers:    {"1": "ответ", ...}
        correct_answers: {"1": {"answer": "правильный", "type": "..."}, ...}

    Returns:
        (score: int, total: int, details: list)
    """
    score   = 0
    total   = len(correct_answers)
    details = []

    for task_id, task_data in correct_answers.items():
        user_ans    = str(user_answers.get(task_id, '')).strip()
        correct_ans = str(task_data.get('answer', '')).strip()
        task_type   = task_data.get('type', 'unknown')

        is_correct = False

        if task_type == 'essay':
            # Сочинение — минимальный объём
            is_correct = len(user_ans.split()) >= 50
        elif not correct_ans:
            # Нет правильного ответа — не засчитываем
            is_correct = False
        else:
            user_norm = normalize(user_ans)
            # Ответ может быть составным: "потомучто или таккак или оттогочто"
            # Разбиваем по " или " и проверяем совпадение с любым вариантом
            variants = [normalize(v) for v in re.split(r'\s+или\s+', correct_ans, flags=re.IGNORECASE)]
            is_correct = user_norm in variants and user_norm != ''

        if is_correct:
            score += 1

        details.append({
            'id':             task_id,
            'correct':        is_correct,
            'user_answer':    user_ans,
            'correct_answer': correct_ans,
            'type':           task_type,
        })

    return score, total, details