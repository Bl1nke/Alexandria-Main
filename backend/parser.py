"""
ПАРСЕР ДЛЯ ВАРИАНТОВ ЕГЭ ПО РУССКОМУ ЯЗЫКУ
Специализированный парсер для формата NeoFamily
"""

import os
import re
import json
from typing import Dict, List, Any
from pypdf import PdfReader


def extract_text_from_pdf(file_path: str) -> str:
    """Извлекает текст из PDF"""
    try:
        reader = PdfReader(file_path)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        raise ValueError(f"Ошибка чтения PDF: {str(e)}")


def parse_variant_pdf(file_path: str) -> List[Dict[str, Any]]:
    """
    Парсит PDF с вариантами заданий ЕГЭ
    Возвращает список заданий
    """
    text = extract_text_from_pdf(file_path)
    tasks = []
    
    # Очищаем текст от лишних пробелов
    text = re.sub(r'\n\s*\n', '\n', text)
    
    # Разбиваем на строки
    lines = text.split('\n')
    
    current_task = None
    task_buffer = []
    in_task_section = True
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Ищем начало задания (цифра с точкой в начале строки)
        task_match = re.match(r'^(\d+)\.\s+(.+)$', line)
        
        if task_match:
            # Сохраняем предыдущее задание
            if current_task and task_buffer:
                current_task['text'] = ' '.join(task_buffer).strip()
                tasks.append(current_task)
                task_buffer = []
            
            task_num = int(task_match.group(1))
            task_text = task_match.group(2).strip()
            
            # Определяем тип задания по номеру
            task_type = determine_task_type(task_num)
            
            current_task = {
                'id': task_num,
                'text': task_text,
                'type': task_type,
                'answer': ''
            }
            task_buffer = [task_text]
            i += 1
            continue
        
        # Если мы внутри задания, собираем текст
        if current_task and line and not line.startswith('ОТВЕТ'):
            # Пропускаем служебные строки
            if not re.match(r'^\d+\.$', line):
                task_buffer.append(line)
        
        i += 1
    
    # Добавляем последнее задание
    if current_task and task_buffer:
        current_task['text'] = ' '.join(task_buffer).strip()
        tasks.append(current_task)
    
    return tasks


def determine_task_type(task_num: int) -> str:
    """Определяет тип задания по номеру"""
    type_map = {
        1: 'union_selection',           # Союз
        2: 'lexical_meaning',            # Лексическое значение
        3: 'text_analysis',              # Анализ текста
        4: 'stress',                     # Ударение
        5: 'paronym',                    # Паронимы
        6: 'word_correction',            # Исправление слова
        7: 'word_form',                  # Форма слова
        8: 'grammar_error',              # Грамматические ошибки
        9: 'root_vowel',                 # Чередующиеся гласные
        10: 'prefix',                    # Приставки
        11: 'suffix',                    # Суффиксы
        12: 'verb_ending',               # Окончания глаголов
        13: 'ne_with_word',              # НЕ с словами
        14: 'union_spelling',            # Союзы
        15: 'nn_spelling',               # НН
        16: 'punctuation_one_comma',     # Одна запятая
        17: 'punctuation_participles',   # Причастия/деепричастия
        18: 'punctuation_intro',         # Вводные слова
        19: 'punctuation_complex',       # Сложное предложение
        20: 'punctuation_complex2',      # Сложное с союзом И
        21: 'dash_usage',                # Тире
        22: 'expressive_means',          # Средства выразительности
        23: 'content_analysis',          # Содержание текста
        24: 'text_features',             # Особенности текста
        25: 'phraseology',               # Фразеологизмы
        26: 'text_connection',           # Средства связи
        27: 'essay'                      # Сочинение
    }
    return type_map.get(task_num, 'unknown')


def parse_answers_pdf(file_path: str) -> Dict[str, str]:
    """
    Парсит PDF с ответами
    Возвращает словарь {номер_задания: ответ}
    """
    text = extract_text_from_pdf(file_path)
    answers = {}
    
    # Ищем таблицу с ответами
    # Формат: номер задания и ответ
    lines = text.split('\n')
    
    in_answers_table = False
    
    for line in lines:
        line = line.strip()
        
        # Ищем начало таблицы ответов
        if 'ответы на задания' in line.lower() or '№ задания' in line:
            in_answers_table = True
            continue
        
        if in_answers_table:
            # Пропускаем заголовки таблицы
            if '№ п/п' in line or 'Ответ' in line or line.startswith('|'):
                continue
            
            # Ищем номер задания и ответ
            # Формат: "| 1 | 80259 | потомучто или таккак |"
            match = re.match(r'\|\s*(\d+)\s*\|\s*\d+\s*\|\s*(.+?)\s*\|', line)
            if match:
                task_num = match.group(1)
                answer = match.group(2).strip()
                # Очищаем ответ
                answer = re.sub(r'\s+', ' ', answer)
                if answer and answer.lower() not in ['решение', '']:
                    answers[task_num] = answer
    
    # Если не нашли в таблице, ищем другие форматы
    if not answers:
        # Ищем паттерны типа "1. ответ" или "1 | ответ"
        patterns = [
            r'(\d+)\s*\|\s*(.+?)(?:\n|$)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                task_num = match[0]
                answer = match[1].strip()
                if answer and len(answer) < 100:
                    answers[task_num] = answer
    
    return answers


def process_variant(variant_path: str, answers_path: str, tasks_dir: str) -> int:
    """
    Основная функция обработки варианта
    """
    os.makedirs(tasks_dir, exist_ok=True)
    
    # 1. Парсим задания
    tasks = parse_variant_pdf(variant_path)
    
    # 2. Парсим ответы
    answers = parse_answers_pdf(answers_path)
    
    # 3. Связываем задания с ответами
    for task in tasks:
        task_id = str(task['id'])
        if task_id in answers:
            task['answer'] = answers[task_id]
    
    # 4. Сохраняем метаданные каждого задания
    for task in tasks:
        task_file = os.path.join(tasks_dir, f'task_{task["id"]}_meta.json')
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump({
                'id': task['id'],
                'text': task['text'],
                'type': task['type'],
                'answer': task['answer']
            }, f, ensure_ascii=False, indent=2)
    
    # 5. Сохраняем ответы для scorer
    correct_answers = {}
    for task in tasks:
        correct_answers[str(task['id'])] = {
            'answer': task['answer'],
            'type': task['type']
        }
    
    answers_json_path = os.path.join(os.path.dirname(tasks_dir), 'answers.json')
    with open(answers_json_path, 'w', encoding='utf-8') as f:
        json.dump(correct_answers, f, ensure_ascii=False, indent=2)
    
    # 6. Сохраняем полную информацию о варианте
    variant_info = {
        'tasks': tasks,
        'answers': answers,
        'total_tasks': len(tasks)
    }
    
    variant_info_path = os.path.join(os.path.dirname(tasks_dir), 'variant_info.json')
    with open(variant_info_path, 'w', encoding='utf-8') as f:
        json.dump(variant_info, f, ensure_ascii=False, indent=2)
    
    return len(tasks)


# Для совместимости
def get_tasks(variant_id: str, uploads_folder: str) -> List[Dict[str, Any]]:
    """Загружает задания из папки"""
    tasks_dir = os.path.join(uploads_folder, variant_id, 'tasks')
    if not os.path.exists(tasks_dir):
        return []
    
    tasks = []
    for filename in sorted(os.listdir(tasks_dir)):
        if filename.startswith('task_') and filename.endswith('_meta.json'):
            with open(os.path.join(tasks_dir, filename), 'r', encoding='utf-8') as f:
                tasks.append(json.load(f))
    return tasks