# backend/server.py
import os
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Импортируем ваши модули. 
# Переименовываем parser в variant_parser, чтобы не конфликтовать со встроенным модулем Python
# import parser as variant_parser
# import scorer

# Временная заглушка для тестирования backend
# Было:
# import parser as variant_parser
# import scorer

# Стало (временно!):
import mock_parser as variant_parser
import mock_scorer as scorer



# === ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ ===
app = Flask(__name__)
CORS(app)  # Разрешает фронтенду (даже с другого порта) делать запросы к серверу

# === НАСТРОЙКИ ПУТЕЙ ===
# os.path.dirname(os.path.abspath(__file__)) → путь к папке, где лежит server.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
DB_FILE = os.path.join(BASE_DIR, 'variants_db.json')

# Создаём папку uploads при первом запуске, если её нет
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Если файла базы нет, создаём пустой список
if not os.path.exists(DB_FILE):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def read_db():
    """Читает variants_db.json. Если файл пустой или битый -> возвращает пустой список"""
    if not os.path.exists(DB_FILE):
        return []
    
    # 1. Проверяем, не пустой ли файл физически
    if os.path.getsize(DB_FILE) == 0:
        return []
        
    # 2. Читаем и парсим с защитой от битого JSON
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            # Если внутри мусор или незакрытые скобки -> тоже считаем пустым
            return []

def write_db(data):
    """Записывает обновлённый список вариантов обратно в файл"""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def safe_filename(original_name):
    """Оставляет только расширение файла, убирая опасные символы из имени"""
    if not original_name or '.' not in original_name:
        return 'file.tmp'
    ext = original_name.rsplit('.', 1)[1].lower()
    return f'variant.{ext}'

# === МАРШРУТЫ (API ENDPOINTS) ===

@app.route('/api/variants', methods=['GET'])
def get_variants():
    """
    GET /api/variants
    Возвращает список всех загруженных вариантов для отображения на главной странице.
    """
    try:
        variants = read_db()
        # Отдаём только безопасные поля, без внутренних путей
        return jsonify([{
            'id': v['id'],
            'name': v['name'],
            'date': v['date'],
            'tasks_count': v['tasks_count'],
            'status': v['status']
        } for v in variants])
    except Exception as e:
        return jsonify({'error': 'Не удалось загрузить список вариантов', 'details': str(e)}), 500


@app.route('/api/upload', methods=['POST'])
def upload_variant():
    """
    POST /api/upload
    Принимает 2 файла: вариант (pdf/docx) и ответы (txt/json/csv).
    Сохраняет, запускает парсер, регистрирует вариант в базе.
    """
    # 1. Проверка наличия файлов
    if 'variant' not in request.files or 'answers' not in request.files:
        return jsonify({'error': 'Отсутствуют файлы. Нужны variant и answers'}), 400

    variant_file = request.files['variant']
    answers_file = request.files['answers']

    if variant_file.filename == '' or answers_file.filename == '':
        return jsonify({'error': 'Файлы не выбраны'}), 400

    # 2. Валидация расширений
    allowed_ext = {'pdf', 'docx'}
    allowed_ans_ext = {'txt', 'json', 'csv'}
    
    v_ext = variant_file.filename.rsplit('.', 1)[1].lower() if '.' in variant_file.filename else ''
    a_ext = answers_file.filename.rsplit('.', 1)[1].lower() if '.' in answers_file.filename else ''

    if v_ext not in allowed_ext:
        return jsonify({'error': f'Формат варианта должен быть PDF или DOCX. Получено: {v_ext}'}), 400
    if a_ext not in allowed_ans_ext:
        return jsonify({'error': f'Формат ответов должен быть TXT, JSON или CSV. Получено: {a_ext}'}), 400

    # 3. Генерация уникального ID и создание структуры папок
    variant_id = str(uuid.uuid4())
    variant_dir = os.path.join(UPLOADS_DIR, variant_id)
    tasks_dir = os.path.join(variant_dir, 'tasks')
    os.makedirs(tasks_dir, exist_ok=True)

    # 4. Сохранение исходных файлов
    variant_path = os.path.join(variant_dir, safe_filename(variant_file.filename))
    answers_path = os.path.join(variant_dir, 'answers_raw.txt')
    
    variant_file.save(variant_path)
    answers_file.save(answers_path)

    # 5. Запуск парсера
    try:
        # variant_parser.process_variant возвращает количество найденных заданий
        tasks_count = variant_parser.process_variant(variant_path, answers_path, tasks_dir)
    except Exception as e:
        # Если парсер упал, чистим папку и возвращаем ошибку
        import shutil
        shutil.rmtree(variant_dir, ignore_errors=True)
        return jsonify({'error': 'Ошибка обработки файла', 'details': str(e)}), 500

    # 6. Запись в базу данных
    new_variant = {
        'id': variant_id,
        'name': variant_file.filename,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'tasks_count': tasks_count,
        'status': 'ready'
    }
    db = read_db()
    db.append(new_variant)
    write_db(db)

    return jsonify({'id': variant_id, 'status': 'ready', 'tasks_count': tasks_count}), 200


@app.route('/api/variants/<variant_id>', methods=['GET'])
def get_variant_details(variant_id):
    """
    GET /api/variants/<id>
    Возвращает список заданий (картинок) для конкретного варианта.
    """
    variant_dir = os.path.join(UPLOADS_DIR, variant_id)
    tasks_dir = os.path.join(variant_dir, 'tasks')

    if not os.path.exists(variant_dir):
        return jsonify({'error': 'Вариант не найден'}), 404

    # Сканируем папку tasks, сортируем по имени, формируем массив
    try:
        task_files = sorted([f for f in os.listdir(tasks_dir) if f.endswith(('.jpg', '.jpeg', '.png'))])
        tasks = []
        for idx, fname in enumerate(task_files, start=1):
            # Формируем относительный путь для фронтенда
            rel_path = f'uploads/{variant_id}/tasks/{fname}'
            tasks.append({
                'number': idx,
                'image_url': rel_path
            })
        
        return jsonify({'id': variant_id, 'tasks': tasks})
    except Exception as e:
        return jsonify({'error': 'Не удалось прочитать задания', 'details': str(e)}), 500


@app.route('/api/variants/<variant_id>/submit', methods=['POST'])
def submit_answers(variant_id):
    """
    POST /api/variants/<id>/submit
    Принимает ответы пользователя, сохраняет, вызывает scorer, возвращает результат.
    """
    variant_dir = os.path.join(UPLOADS_DIR, variant_id)
    if not os.path.exists(variant_dir):
        return jsonify({'error': 'Вариант не найден'}), 404

    # 1. Получаем JSON с ответами от фронтенда
    data = request.get_json()
    if not data or 'answers' not in data:
        return jsonify({'error': 'Нет данных с ответами'}), 400

    user_answers = data['answers']

    # 2. Сохраняем ответы пользователя на диск
    user_answers_path = os.path.join(variant_dir, 'user_answers.json')
    with open(user_answers_path, 'w', encoding='utf-8') as f:
        json.dump(user_answers, f, ensure_ascii=False, indent=2)

    # 3. Загружаем эталонные ответы
    correct_answers_path = os.path.join(variant_dir, 'answers.json')
    if not os.path.exists(correct_answers_path):
        return jsonify({'error': 'Файл с правильными ответами не найден'}), 404

    with open(correct_answers_path, 'r', encoding='utf-8') as f:
        correct_answers = json.load(f)

    # 4. Вызываем модуль проверки
    try:
        score, total, details = scorer.calculate_score(user_answers, correct_answers)
    except Exception as e:
        return jsonify({'error': 'Ошибка при проверке', 'details': str(e)}), 500

    return jsonify({
        'score': score,
        'total': total,
        'percentage': round((score / total * 100), 1) if total > 0 else 0,
        'details': details
    }), 200


# === ОТДАЧА СТАТИЧЕСКИХ ФАЙЛОВ (КАРТИНОК) ===
# Фронтенд будет запрашивать картинки по пути /uploads/...
# Этот маршрут говорит Flask: "возьми файл из папки uploads и отдай браузеру"
@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    return send_from_directory(UPLOADS_DIR, filename)


# === ОБРАБОТКА ОШИБОК ===
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Запрос не найден'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


# === ЗАПУСК СЕРВЕРА ===
if __name__ == '__main__':
    # debug=True → сервер перезагружается при изменении кода
    # НЕ использовать debug=True при хостинге. Дыры безопасности
    # port=5000 → стандартный порт Flask
    print("Сервер запущен на http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)