"""
МОДУЛЬ ПРОВЕРКИ ДЛЯ ЕГЭ
"""

import re


def calculate_score(user_answers: dict, correct_answers: dict):
    """
    Проверяет ответы пользователя
    
    Args:
        user_answers: {"1": "ответ1", "2": "ответ2", ...}
        correct_answers: {"1": {"answer": "правильный1", "type": "text_analysis"}, ...}
    
    Returns:
        score, total, details
    """
    score = 0
    total = len(correct_answers)
    details = []
    
    for task_id, task_data in correct_answers.items():
        user_ans = str(user_answers.get(task_id, "")).strip()
        correct_ans = str(task_data.get("answer", "")).strip()
        task_type = task_data.get("type", "unknown")
        
        is_correct = False
        
        # Разная логика проверки для разных типов заданий
        if task_type == "essay":
            # Сочинение проверяется вручную
            is_correct = len(user_ans) > 150  # Минимальная длина
        elif task_type in ["orthography", "grammar", "punctuation"]:
            # Точное совпадение или с небольшой нормализацией
            is_correct = normalize_answer(user_ans) == normalize_answer(correct_ans)
        else:
            # Для остальных типов - нестрогое сравнение
            is_correct = user_ans.lower() == correct_ans.lower()
        
        if is_correct:
            score += 1
        
        details.append({
            "id": task_id,
            "correct": is_correct,
            "correct_answer": correct_ans,
            "user_answer": user_ans,
            "type": task_type
        })
    
    return score, total, details


def normalize_answer(answer: str) -> str:
    """Нормализует ответ для сравнения"""
    # Убираем лишние пробелы, приводим к нижнему регистру
    answer = answer.strip().lower()
    # Убираем лишние пробелы между словами
    answer = re.sub(r'\s+', ' ', answer)
    return answer