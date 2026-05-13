"""
МОДУЛЬ ПАРСЕРА ДЛЯ АЛЕКСАНДРИИ
Принимает: файл с заданиями (PDF/DOCX) и файл с ответами (TXT/JSON/CSV)
"""

import os
import json
import re
from typing import List, Dict, Any
from pypdf import PdfReader
from docx import Document


# ============================================================================
# ИЗВЛЕЧЕНИЕ ТЕКСТА ИЗ ФАЙЛА ЗАДАНИЙ
# ============================================================================

def _extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    return "\n".join(text_parts)


def _extract_text_from_docx(file_path: str) -> str:
    doc = Document(file_path)
    paragraphs = []
    for para in doc.paragraphs:
        if para.text.strip():
            paragraphs.append(para.text)
    return "\n".join(paragraphs)


# ============================================================================
# ПАРСИНГ ФАЙЛА С ОТВЕТАМИ
# ============================================================================

def _parse_answers_file(file_path: str) -> Dict[str, str]:
    """
    Читает файл с ответами и возвращает словарь {номер_задания: ответ}
    Поддерживает TXT, JSON, CSV
    """
    ext = os.path.splitext(file_path)[1].lower()
    answers = {}

    if ext == '.json':
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    answers[str(k)] = str(v).strip()
            elif isinstance(data, list):
                for item in data:
                    if 'id' in item and 'answer' in item:
                        answers[str(item['id'])] = str(item['answer']).strip()

    elif ext == '.csv':
        import csv
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    answers[str(row[0].strip())] = row[1].strip()

    elif ext == '.txt':
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                match = re.match(r'^(\d+)[\.:\)\s]+(.+)$', line)
                if match:
                    answers[match.group(1)] = match.group(2).strip()

    return answers


# ============================================================================
# ОПРЕДЕЛЕНИЕ ТИПА ОТВЕТА
# ============================================================================

def _detect_answer_type(answer: str) -> str:
    answer = answer.strip()
    if re.match(r'^-?\d+[.,]?\d*$', answer.replace(',', '.')):
        return "number"
    if re.match(r'^[А-ЕA-E]\)?$', answer):
        return "choice"
    return "text"


# ============================================================================
# РАЗБИВКА ТЕКСТА НА ЗАДАНИЯ
# ============================================================================

def _split_into_tasks(text: str, answers_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Разбивает текст на задания и связывает с ответами из файла
    """
    tasks = []

    # Ищем задания по паттерну: номер. текст задания
    pattern = r'(?:Задание\s*)?(\d+)[\.\)]\s*(.+?)(?=(?:\n\s*(?:Задание\s*)?\d+[\.\)]|\Z))'
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)

    for match in matches:
        task_num = int(match[0])
        task_text = match[1].strip()
        task_text = re.sub(r'\n+', ' ', task_text)

        # Берём ответ из файла ответов
        answer = answers_map.get(str(task_num), "")

        tasks.append({
            "id": task_num,
            "text": task_text,
            "answer": answer,
            "type": _detect_answer_type(answer)
        })

    tasks.sort(key=lambda x: x["id"])
    return tasks


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ — ВЫЗЫВАЕТСЯ ИЗ SERVER.PY
# ============================================================================

def process_variant(variant_path: str, answers_path: str, tasks_dir: str) -> int:
    """
    Функция для server.py.

    Аргументы:
        variant_path (str): путь к PDF/DOCX с заданиями
        answers_path (str): путь к TXT/JSON/CSV с ответами
        tasks_dir (str): папка для сохранения заданий

    Возвращает:
        int: количество найденных заданий
    """

    # 1. Парсим файл с ответами
    answers_map = _parse_answers_file(answers_path)

    # 2. Извлекаем текст из файла заданий
    ext = os.path.splitext(variant_path)[1].lower()
    if ext == '.pdf':
        text = _extract_text_from_pdf(variant_path)
    if ext == '.docx':
        text = _extract_text_from_docx(variant_path)

    if not text or not text.strip():
        raise ValueError("Не удалось извлечь текст из файла заданий")

    # 3. Разбиваем на задания и связываем с ответами
    tasks = _split_into_tasks(text, answers_map)

    if not tasks:
        raise ValueError("Не найдено заданий в файле")

    # 4. Создаём папку для заданий
    os.makedirs(tasks_dir, exist_ok=True)

    # 5. Сохраняем каждое задание (только текст, без ответа)
    for task in tasks:
        task_file = os.path.join(tasks_dir, f'task_{task["id"]}.json')
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump({
                'id': task['id'],
                'text': task['text'],
                'type': task['type']
            }, f, ensure_ascii=False, indent=2)

    # 6. Сохраняем answers.json (эталонные ответы для scorer.py)
    correct_answers = {}
    for task in tasks:
        correct_answers[str(task['id'])] = {
            'answer': task['answer'],
            'type': task['type']
        }

    parent_dir = os.path.dirname(tasks_dir)
    answers_json_path = os.path.join(parent_dir, 'answers.json')
    with open(answers_json_path, 'w', encoding='utf-8') as f:
        json.dump(correct_answers, f, ensure_ascii=False, indent=2)

    # 7. Возвращаем количество заданий
    return len(tasks)


# ============================================================================
# ДОПОЛНИТЕЛЬНАЯ ФУНКЦИЯ
# ============================================================================

def get_tasks(variant_id: str, uploads_folder: str) -> List[Dict[str, Any]]:
    """Загружает задания из папки"""
    tasks_dir = os.path.join(uploads_folder, variant_id, 'tasks')
    if not os.path.exists(tasks_dir):
        return []

    tasks = []
    for filename in sorted(os.listdir(tasks_dir)):
        if filename.startswith('task_') and filename.endswith('.json'):
            with open(os.path.join(tasks_dir, filename), 'r', encoding='utf-8') as f:
                tasks.append(json.load(f))
    return tasks