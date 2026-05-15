document.addEventListener('DOMContentLoaded', () => {
    // === DOM ЭЛЕМЕНТЫ ===
    const listScreen = document.getElementById('list-screen');
    const uploadModal = document.getElementById('upload-modal-overlay');
    const solverScreen = document.getElementById('solver-screen');
    const resultsContainer = document.getElementById('results-container');

    const openUploadModalBtn = document.getElementById('open-upload-modal-btn');
    const variantsListContainer = document.getElementById('variants-list-container');
    const currentVariantTitle = document.getElementById('current-variant-title');

    const closeUploadModalBtn = document.getElementById('close-upload-modal-btn');
    const cancelUploadModalBtn = document.getElementById('cancel-upload-modal-btn');
    const submitUploadBtn = document.getElementById('submit-upload-btn');

    const taskDropZone = document.getElementById('task-drop-zone');
    const taskFileInput = document.getElementById('task-file-input');
    const taskFileNameSpan = document.getElementById('task-file-name');
    
    const answersDropZone = document.getElementById('answers-drop-zone');
    const answersFileInput = document.getElementById('answers-file-input');
    const answersFileNameSpan = document.getElementById('answers-file-name');

    const tasksContainer = document.getElementById('tasks-container');
    const submitAnswersBtn = document.getElementById('submit-answers-btn');
    const cancelSolverBtn = document.getElementById('cancel-solver-btn');
    const scoreDisplay = document.getElementById('score-display');
    const backToListBtn = document.getElementById('back-to-list-btn');

    // === СОСТОЯНИЕ ===
    let currentTaskFiles = { tasks: null, answers: null };
    let activeVariantId = null;
    let userAnswers = {};

    const API_BASE_URL = 'http://127.0.0.1:5000/api';

    // === УПРАВЛЕНИЕ ЭКРАНАМИ ===
    function showScreen(screenToShow) {
        [listScreen, uploadModal, solverScreen].forEach(screen => {
            if (screen) screen.classList.add('hidden');
        });
        resultsContainer.classList.add('hidden');
        if (screenToShow) {
            screenToShow.classList.remove('hidden');
            if (screenToShow === uploadModal) {
                setTimeout(() => screenToShow.classList.add('active'), 10);
                document.body.style.overflow = 'hidden';
            } else {
                document.body.style.overflow = '';
            }
        }
    }

    function openUploadModal() {
        currentTaskFiles = { tasks: null, answers: null };
        taskFileNameSpan.textContent = '';
        answersFileNameSpan.textContent = '';
        taskFileInput.value = '';
        answersFileInput.value = '';
        showScreen(uploadModal);
    }

    function closeUploadModal() {
        uploadModal.classList.remove('active');
        setTimeout(() => {
            showScreen(listScreen);
            document.body.style.overflow = '';
        }, 300);
    }

    // === ЗАГРУЗКА ФАЙЛОВ ===
    function handleFileSelection(files, type, fileNameSpan) {
        if (files.length > 0) {
            const file = files[0];
            currentTaskFiles[type] = file;
            fileNameSpan.textContent = file.name;
        } else {
            currentTaskFiles[type] = null;
            fileNameSpan.textContent = '';
        }
    }

    async function sendFilesToServer() {
        if (!currentTaskFiles.tasks || !currentTaskFiles.answers) {
            alert('Пожалуйста, загрузите оба файла: заданий и ответов.');
            return;
        }

        const formData = new FormData();
        // ИСПРАВЛЕНО: имена полей должны совпадать с бэкендом
        formData.append('variant', currentTaskFiles.tasks);
        formData.append('answers', currentTaskFiles.answers);

        try {
            // ИСПРАВЛЕНО: правильный эндпоинт
            const response = await fetch(`${API_BASE_URL}/upload`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Ошибка при загрузке');
            }

            const result = await response.json();
            alert('Вариант успешно загружен!');
            closeUploadModal();
            fetchVariants();

        } catch (error) {
            console.error('Ошибка загрузки:', error);
            alert(`Ошибка: ${error.message}`);
        }
    }

    // Drag-and-Drop обработчики
    [taskDropZone, answersDropZone].forEach(zone => {
        const type = zone.id === 'task-drop-zone' ? 'tasks' : 'answers';
        const fileInput = zone.querySelector('input[type="file"]');
        const fileNameSpan = zone.querySelector('span');

        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.style.borderColor = 'var(--purple-dark)';
            zone.style.backgroundColor = 'rgba(157, 125, 250, 0.1)';
        });
        zone.addEventListener('dragleave', () => {
            zone.style.borderColor = 'var(--border-gray)';
            zone.style.backgroundColor = 'transparent';
        });
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.style.borderColor = 'var(--border-gray)';
            zone.style.backgroundColor = 'transparent';
            handleFileSelection(e.dataTransfer.files, type, fileNameSpan);
        });

        zone.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', (e) => handleFileSelection(e.target.files, type, fileNameSpan));
    });

    // === СПИСОК ВАРИАНТОВ ===
    async function fetchVariants() {
        try {
            const response = await fetch(`${API_BASE_URL}/variants`);
            if (!response.ok) throw new Error('Не удалось получить список вариантов');
            const variants = await response.json();
            renderVariants(variants);
        } catch (error) {
            console.error('Ошибка:', error);
            variantsListContainer.innerHTML = `<p class="text-grey text-center">Ошибка: ${error.message}</p>`;
        }
    }

    function renderVariants(variants) {
        variantsListContainer.innerHTML = '';
        if (variants.length === 0) {
            variantsListContainer.innerHTML = `<p class="text-grey text-center">Нет загруженных вариантов.</p>`;
            return;
        }

        variants.forEach(variant => {
            const variantDiv = document.createElement('div');
            variantDiv.className = 'variant-item';
            variantDiv.dataset.variantId = variant.id;

            const titleSpan = document.createElement('span');
            titleSpan.textContent = variant.name;
            variantDiv.appendChild(titleSpan);

            const startBtn = document.createElement('button');
            startBtn.className = 'start-btn';
            startBtn.textContent = 'Решать';
            startBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                startSolving(variant.id, variant.name);
            });
            variantDiv.appendChild(startBtn);

            variantsListContainer.appendChild(variantDiv);
        });
    }

    // === РЕШАТЕЛЬ ===
    async function startSolving(variantId, variantTitle) {
        activeVariantId = variantId;
        userAnswers = {};
        currentVariantTitle.textContent = variantTitle;
        showScreen(solverScreen);
        await fetchVariantTasks(variantId);
    }

    async function fetchVariantTasks(variantId) {
        tasksContainer.innerHTML = '<p class="text-grey text-center">Загрузка...</p>';
        try {
            // ИСПРАВЛЕНО: правильный эндпоинт
            const response = await fetch(`${API_BASE_URL}/variants/${variantId}`);
            if (!response.ok) throw new Error('Не удалось получить задания');
            const data = await response.json();
            renderTasks(data.tasks);
        } catch (error) {
            console.error('Ошибка:', error);
            tasksContainer.innerHTML = `<p class="text-red-500">Ошибка: ${error.message}</p>`;
        }
    }

function renderTasks(tasks) {
    tasksContainer.innerHTML = '';
    
    if (!tasks || tasks.length === 0) {
        tasksContainer.innerHTML = '<p class="text-center text-gray-500">Задания не загружены</p>';
        return;
    }
    
    // Сортируем задания по номеру
    tasks.sort((a, b) => a.id - b.id);
    
    tasks.forEach(task => {
        const taskDiv = document.createElement('div');
        taskDiv.className = 'task-card bg-white rounded-xl p-6 mb-6 shadow-md';
        
        // Заголовок задания
        const taskHeader = document.createElement('div');
        taskHeader.className = 'task-header mb-4';
        const taskNumber = document.createElement('h3');
        taskNumber.className = 'text-xl font-bold text-gray-800 mb-2';
        taskNumber.textContent = `Задание ${task.id}`;
        
        // Тип задания
        const taskType = document.createElement('span');
        taskType.className = 'inline-block px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm';
        taskType.textContent = getTaskTypeName(task.type);
        
        taskHeader.appendChild(taskNumber);
        taskHeader.appendChild(taskType);
        taskDiv.appendChild(taskHeader);
        
        // Текст задания
        const taskText = document.createElement('div');
        taskText.className = 'task-text text-gray-700 mb-4 leading-relaxed';
        taskText.textContent = task.text || 'Текст задания отсутствует';
        taskDiv.appendChild(taskText);
        
        // Поле для ответа
        const answerContainer = document.createElement('div');
        answerContainer.className = 'answer-container';
        
        const answerLabel = document.createElement('label');
        answerLabel.className = 'block text-sm font-medium text-gray-700 mb-2';
        answerLabel.textContent = 'Ваш ответ:';
        
        const answerInput = document.createElement('input');
        answerInput.type = 'text';
        answerInput.className = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent';
        answerInput.placeholder = 'Введите ответ...';
        answerInput.dataset.taskId = task.id;
        
        // Событие для сохранения ответа
        answerInput.addEventListener('input', (e) => {
            userAnswers[task.id] = e.target.value.trim();
        });
        
        answerContainer.appendChild(answerLabel);
        answerContainer.appendChild(answerInput);
        taskDiv.appendChild(answerContainer);
        
        tasksContainer.appendChild(taskDiv);
    });
}

function getTaskTypeName(type) {
    const types = {
        'union_selection': 'Выбор союза',
        'lexical_meaning': 'Лексика',
        'text_analysis': 'Анализ текста',
        'stress': 'Ударение',
        'paronym': 'Паронимы',
        'word_correction': 'Исправление слова',
        'word_form': 'Форма слова',
        'grammar_error': 'Грамматика',
        'root_vowel': 'Корни',
        'prefix': 'Приставки',
        'suffix': 'Суффиксы',
        'verb_ending': 'Глаголы',
        'ne_with_word': 'НЕ с словами',
        'union_spelling': 'Союзы',
        'nn_spelling': 'НН',
        'punctuation_one_comma': 'Пунктуация',
        'punctuation_participles': 'Обороты',
        'punctuation_intro': 'Вводные слова',
        'punctuation_complex': 'Сложное предложение',
        'punctuation_complex2': 'Сложное с И',
        'dash_usage': 'Тире',
        'expressive_means': 'Средства выразительности',
        'content_analysis': 'Содержание',
        'text_features': 'Особенности текста',
        'phraseology': 'Фразеология',
        'text_connection': 'Связь предложений',
        'essay': 'Сочинение',
        'unknown': 'Задание'
    };
    return types[type] || 'Задание';
}

    // === ОТПРАВКА ОТВЕТОВ ===
    function collectAnswers() {
        // Собираем ответы из input-полей
        const inputs = document.querySelectorAll('.task-answer-input');
        inputs.forEach(input => {
            const id = input.dataset.taskId;
            userAnswers[id] = input.value.trim();
        });
        return userAnswers;
    }

    async function submitAnswers() {
        if (!activeVariantId) {
            alert('Выберите вариант для решения.');
            return;
        }

        const answers = collectAnswers();

        try {
            // ИСПРАВЛЕНО: правильный эндпоинт
            const response = await fetch(`${API_BASE_URL}/variants/${activeVariantId}/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ answers }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Ошибка проверки');
            }

            const result = await response.json();
            displayResults(result);

        } catch (error) {
            console.error('Ошибка:', error);
            alert(`Ошибка: ${error.message}`);
        }
    }

    function displayResults(results) {
        scoreDisplay.textContent = `${results.score} из ${results.total} (${results.percentage}%)`;
        resultsContainer.classList.remove('hidden');
        resultsContainer.scrollIntoView({ behavior: 'smooth' });
    }

    // === ИНИЦИАЛИЗАЦИЯ ===
    function initializeApp() {
        showScreen(listScreen);
        fetchVariants();

        openUploadModalBtn.addEventListener('click', openUploadModal);
        closeUploadModalBtn.addEventListener('click', closeUploadModal);
        cancelUploadModalBtn.addEventListener('click', closeUploadModal);
        submitUploadBtn.addEventListener('click', sendFilesToServer);
        
        submitAnswersBtn.addEventListener('click', submitAnswers);
        cancelSolverBtn.addEventListener('click', () => showScreen(listScreen));
        backToListBtn.addEventListener('click', () => {
            resultsContainer.classList.add('hidden');
            showScreen(listScreen);
        });
    }

    initializeApp();
});