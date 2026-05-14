document.addEventListener('DOMContentLoaded', () => {
    // --- 1. DOM ЭЛЕМЕНТЫ (Ссылки на HTML-элементы) ---
    // Экраны
    const listScreen = document.getElementById('list-screen');
    const uploadModal = document.getElementById('upload-modal-overlay');
    const solverScreen = document.getElementById('solver-screen');
    const resultsContainer = document.getElementById('results-container');

    // Кнопки и элементы списка вариантов
    const openUploadModalBtn = document.getElementById('open-upload-modal-btn');
    const variantsListContainer = document.getElementById('variants-list-container');
    const currentVariantTitle = document.getElementById('current-variant-title');

    // Элементы модалки загрузки
    const closeUploadModalBtn = document.getElementById('close-upload-modal-btn');
    const cancelUploadModalBtn = document.getElementById('cancel-upload-modal-btn');
    const submitUploadBtn = document.getElementById('submit-upload-btn');

    const taskDropZone = document.getElementById('task-drop-zone');
    const taskFileInput = document.getElementById('task-file-input');
    const taskFileNameSpan = document.getElementById('task-file-name');
    
    const answersDropZone = document.getElementById('answers-drop-zone');
    const answersFileInput = document.getElementById('answers-file-input');
    const answersFileNameSpan = document.getElementById('answers-file-name');

    // Элементы решателя
    const tasksContainer = document.getElementById('tasks-container');
    const submitAnswersBtn = document.getElementById('submit-answers-btn');
    const cancelSolverBtn = document.getElementById('cancel-solver-btn');
    const scoreDisplay = document.getElementById('score-display');
    const backToListBtn = document.getElementById('back-to-list-btn');

    // --- 2. ПЕРЕМЕННЫЕ СОСТОЯНИЯ (Для хранения данных приложения) ---
    let currentTaskFiles = { tasks: null, answers: null }; // Файлы для загрузки
    let activeVariantId = null; // ID текущего решаемого варианта
    let userAnswers = {}; // Ответы пользователя для текущего варианта
    let drawingCanvases = {}; // Для хранения состояния рисования по ID задания

    const API_BASE_URL = 'http://127.0.0.1:5000/api'; // Адрес твоего бэкенда Flask (убедись, что он правильный)

    // --- 3. ФУНКЦИИ УПРАВЛЕНИЯ ЭКРАНАМИ ---

    /**
     * Показывает указанный экран, скрывая все остальные.
     * @param {HTMLElement} screenToShow - Элемент экрана, который нужно показать.
     */
    function showScreen(screenToShow) {
        [listScreen, uploadModal, solverScreen].forEach(screen => {
            if (screen) screen.classList.add('hidden');
        });
        resultsContainer.classList.add('hidden'); // Скрываем результаты при переключении
        if (screenToShow) {
            screenToShow.classList.remove('hidden');
            // Если показываем модалку, добавляем класс 'active' для CSS-анимаций
            if (screenToShow === uploadModal) {
                setTimeout(() => screenToShow.classList.add('active'), 10); // Небольшая задержка для анимации
                document.body.style.overflow = 'hidden'; // Запрещаем скролл
            } else {
                document.body.style.overflow = ''; // Разрешаем скролл
            }
        }
    }

    /** Открывает модальное окно загрузки. */
    function openUploadModal() {
        // Очищаем предыдущие файлы и имена
        currentTaskFiles = { tasks: null, answers: null };
        taskFileNameSpan.textContent = '';
        answersFileNameSpan.textContent = '';
        taskFileInput.value = '';
        answersFileInput.value = '';

        showScreen(uploadModal);
    }

    /** Закрывает модальное окно загрузки. */
    function closeUploadModal() {
        uploadModal.classList.remove('active'); // Убираем активный класс для анимации
        setTimeout(() => {
            showScreen(listScreen); // После анимации возвращаемся к списку
            document.body.style.overflow = ''; // Разрешаем скролл
        }, 300); // Должно соответствовать transition в CSS
    }

    // --- 4. ЛОГИКА ЗАГРУЗКИ ФАЙЛОВ ---

    /**
     * Обрабатывает выбор файла через input или drag-and-drop.
     * @param {FileList} files - Список файлов.
     * @param {string} type - 'tasks' или 'answers'.
     * @param {HTMLElement} fileNameSpan - Элемент для отображения имени файла.
     */
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

    /** Отправляет файлы заданий и ответов на сервер. */
    async function sendFilesToServer() {
        if (!currentTaskFiles.tasks || !currentTaskFiles.answers) {
            alert('Пожалуйста, загрузите оба файла: заданий и ответов.');
            return;
        }

        const formData = new FormData();
        formData.append('tasks_file', currentTaskFiles.tasks);
        formData.append('answers_file', currentTaskFiles.answers);

        try {
            const response = await fetch(`${API_BASE_URL}/upload-variant`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Ошибка при загрузке файлов');
            }

            const result = await response.json();
            alert(result.message);
            closeUploadModal();
            fetchVariants(); // Обновляем список вариантов после успешной загрузки

        } catch (error) {
            console.error('Ошибка загрузки:', error);
            alert(`Ошибка: ${error.message}`);
        }
    }

    // Обработчики Drag-and-Drop для taskDropZone
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

        // Обработчик для клика по drop-зоне (открытие диалога выбора файла)
        zone.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', (e) => handleFileSelection(e.target.files, type, fileNameSpan));
    });

    // --- 5. ЛОГИКА СПИСКА ВАРИАНТОВ ---

    /** Получает список всех вариантов с сервера и отображает их. */
    async function fetchVariants() {
        try {
            const response = await fetch(`${API_BASE_URL}/variants`);
            if (!response.ok) {
                throw new Error('Не удалось получить список вариантов');
            }
            const variants = await response.json();
            renderVariants(variants);
        } catch (error) {
            console.error('Ошибка при получении списка вариантов:', error);
            variantsListContainer.innerHTML = `<p class="text-grey text-center">Ошибка загрузки вариантов: ${error.message}</p>`;
        }
    }

    /**
     * Динамически создает HTML-элементы для каждого варианта в списке.
     * @param {Array<Object>} variants - Массив объектов вариантов.
     */
    function renderVariants(variants) {
        variantsListContainer.innerHTML = ''; // Очищаем контейнер

        if (variants.length === 0) {
            variantsListContainer.innerHTML = `<p class="text-grey text-center">Пока нет загруженных вариантов.</p>`;
            return;
        }

        variants.forEach(variant => {
            const variantDiv = document.createElement('div');
            variantDiv.className = 'variant-item'; // Класс для стилизации в CSS
            variantDiv.dataset.variantId = variant.id; // Храним ID в data-атрибуте

            const titleSpan = document.createElement('span');
            titleSpan.textContent = variant.title;
            variantDiv.appendChild(titleSpan);

            const startBtn = document.createElement('button');
            startBtn.className = 'start-btn';
            startBtn.textContent = 'Решать';
            startBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // Останавливаем всплытие, чтобы не срабатывал клик по всей строке
                startSolving(variant.id, variant.title);
            });
            variantDiv.appendChild(startBtn);

            variantsListContainer.appendChild(variantDiv);
        });
    }

    // --- 6. ЛОГИКА РЕШАТЕЛЯ ЗАДАНИЙ ---

    /**
     * Инициализирует экран решателя для выбранного варианта.
     * @param {string} variantId - ID выбранного варианта.
     * @param {string} variantTitle - Название выбранного варианта.
     */
    async function startSolving(variantId, variantTitle) {
        activeVariantId = variantId;
        userAnswers = {}; // Сбрасываем ответы пользователя
        drawingCanvases = {}; // Сбрасываем состояние рисования
        currentVariantTitle.textContent = variantTitle;
        showScreen(solverScreen);
        await fetchVariantTasks(variantId);
    }

    /** Получает задания для текущего варианта и отображает их. */
    async function fetchVariantTasks(variantId) {
        tasksContainer.innerHTML = '<p class="text-grey text-center">Загрузка заданий...</p>';
        try {
            const response = await fetch(`${API_BASE_URL}/variant/${variantId}/tasks`);
            if (!response.ok) {
                throw new Error('Не удалось получить задания варианта');
            }
            const tasks = await response.json();
            renderTasks(tasks);
        } catch (error) {
            console.error('Ошибка при получении заданий:', error);
            tasksContainer.innerHTML = `<p class="text-red-500 text-center">Ошибка: ${error.message}</p>`;
        }
    }

    /**
     * Динамически создает HTML для каждого задания (картинка, canvas, поле ввода).
     * @param {Array<Object>} tasks - Массив объектов заданий.
     */
    function renderTasks(tasks) {
        tasksContainer.innerHTML = '';
        tasks.forEach(task => {
            const taskDiv = document.createElement('div');
            taskDiv.className = 'task-item'; // Класс для стилизации

            const taskTitle = document.createElement('h4');
            taskTitle.textContent = `Задание ${task.id}`;
            taskDiv.appendChild(taskTitle);

            if (task.image_url) { // Если у задания есть изображение
                const imgContainer = document.createElement('div');
                imgContainer.className = 'task-image-container';
                const taskImage = document.createElement('img');
                taskImage.className = 'task-image';
                taskImage.src = task.image_url; // URL изображения с сервера
                taskImage.alt = `Задание ${task.id}`;
                imgContainer.appendChild(taskImage);
                taskDiv.appendChild(imgContainer);
            }

            // Создаем canvas для рисования
            const canvas = document.createElement('canvas');
            canvas.className = 'task-canvas';
            canvas.width = 400; // Пример, нужно будет подобрать оптимальный размер
            canvas.height = 200; // или динамически из task.image_size
            const ctx = canvas.getContext('2d');
            ctx.lineWidth = 2;
            ctx.strokeStyle = 'blue'; // Цвет линии
            
            taskDiv.appendChild(canvas);
            
            // Сохраняем состояние рисования
            drawingCanvases[task.id] = {
                canvas: canvas,
                ctx: ctx,
                isDrawing: false,
                lastX: 0,
                lastY: 0
            };
            
            // Добавляем слушателей для рисования
            canvas.addEventListener('mousedown', (e) => startDrawing(e, task.id));
            canvas.addEventListener('mousemove', (e) => draw(e, task.id));
            canvas.addEventListener('mouseup', () => stopDrawing(task.id));
            canvas.addEventListener('mouseout', () => stopDrawing(task.id)); // Останавливать рисование при уходе мыши

            // Поле ввода для текстового ответа
            const answerInput = document.createElement('input');
            answerInput.type = 'text';
            answerInput.className = 'task-answer-input';
            answerInput.placeholder = 'Введите ваш ответ или нарисуйте на холсте';
            answerInput.addEventListener('input', (e) => {
                userAnswers[task.id] = e.target.value; // Сохраняем текстовый ответ
            });
            taskDiv.appendChild(answerInput);

            tasksContainer.appendChild(taskDiv);
        });
    }

    // --- 7. ЛОГИКА РИСОВАНИЯ НА CANVAS ---
    function startDrawing(e, taskId) {
        const drawState = drawingCanvases[taskId];
        if (!drawState) return;

        drawState.isDrawing = true;
        [drawState.lastX, drawState.lastY] = [e.offsetX, e.offsetY]; // Начальная точка
    }

    function draw(e, taskId) {
        const drawState = drawingCanvases[taskId];
        if (!drawState || !drawState.isDrawing) return;

        const ctx = drawState.ctx;
        ctx.beginPath(); // Начать новый путь
        ctx.moveTo(drawState.lastX, drawState.lastY); // Передвинуть к последней точке
        ctx.lineTo(e.offsetX, e.offsetY); // Линия до текущей точки
        ctx.stroke(); // Нарисовать линию
        
        [drawState.lastX, drawState.lastY] = [e.offsetX, e.offsetY]; // Обновить последнюю точку
    }

    function stopDrawing(taskId) {
        const drawState = drawingCanvases[taskId];
        if (drawState) drawState.isDrawing = false;
    }

    // --- 8. СБОР И ОТПРАВКА ОТВЕТОВ ---

    /** Собирает все ответы пользователя (текстовые и с canvas). */
    function collectAnswers() {
        // Проходим по всем canvas для рисованных ответов
        for (const taskId in drawingCanvases) {
            const drawState = drawingCanvases[taskId];
            // Сохраняем изображение canvas как Base64 строку
            userAnswers[taskId] = drawState.canvas.toDataURL('image/png');
        }
        // Текстовые ответы уже сохраняются по событию 'input'
        console.log('Собранные ответы:', userAnswers);
        return userAnswers;
    }

    /** Отправляет собранные ответы на сервер для проверки. */
    async function submitAnswers() {
        if (!activeVariantId) {
            alert('Сначала выберите вариант для решения.');
            return;
        }

        const answers = collectAnswers();

        try {
            const response = await fetch(`${API_BASE_URL}/submit-answers/${activeVariantId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(answers),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Ошибка при отправке ответов');
            }

            const result = await response.json();
            console.log('Результаты проверки:', result);
            displayResults(result); // Показать результаты пользователю

        } catch (error) {
            console.error('Ошибка отправки ответов:', error);
            alert(`Ошибка: ${error.message}`);
        }
    }

    /** Отображает полученные результаты проверки. */
    function displayResults(results) {
        scoreDisplay.textContent = results.score; // Обновляем баллы
        // Здесь можно добавить более детальную информацию о результатах
        resultsContainer.classList.remove('hidden'); // Показываем блок результатов
        // Можно проскроллить к результатам:
        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }


    // --- 9. ИНИЦИАЛИЗАЦИЯ (Запуск при загрузке страницы) ---
    function initializeApp() {
        // Устанавливаем начальный экран
        showScreen(listScreen);
        fetchVariants(); // Загружаем список вариантов

        // Назначаем слушателей событий
        openUploadModalBtn.addEventListener('click', openUploadModal);
        closeUploadModalBtn.addEventListener('click', closeUploadModal);
        cancelUploadModalBtn.addEventListener('click', closeUploadModal);
        submitUploadBtn.addEventListener('click', sendFilesToServer);
        
        submitAnswersBtn.addEventListener('click', submitAnswers);
        cancelSolverBtn.addEventListener('click', () => showScreen(listScreen));
        backToListBtn.addEventListener('click', () => {
            resultsContainer.classList.add('hidden'); // Скрываем результаты
            showScreen(listScreen);
        });

        // Запуск Lucide Icons (должно быть в index.html после script.js)
        // lucide.createIcons();
    }

    initializeApp(); // Запускаем приложение
});