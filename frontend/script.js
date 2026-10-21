const API = 'http://127.0.0.1:5000/api';

async function apiFetch(url, opts = {}, ms = 10000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { ...opts, signal: ctrl.signal });
  } catch (e) {
    if (e.name === 'AbortError') {
      throw new Error(`Сервер не ответил за ${ms / 1000} с. Flask запущен?`);
    }
    if (e.message.toLowerCase().includes('failed to fetch')) {
      throw new Error('Нет соединения. Запустите сервер командой: python server.py');
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

const state = {
  files: { variant: null, answers: null },
  variantId: null,
  variantName: '',
  answers: {},
  searchQuery: '',
};

const $ = id => document.getElementById(id);

function isUploadModalOpen() {
  return !$('modal-upload').classList.contains('hidden');
}

// К какому экрану относится пункт меню в шапке («Варианты» — список, «Профиль» — профиль).
const NAV_SECTIONS = { variants: ['list'], profile: ['profile'] };

// Подсветка активного пункта меню: вызывается при каждом переключении экрана.
function updateNavActive(screenName) {
  document.querySelectorAll('[data-nav]').forEach(item => {
    const isActive = (NAV_SECTIONS[item.dataset.nav] || []).includes(screenName);
    item.classList.toggle('is-active', isActive);
    if (isActive) item.setAttribute('aria-current', 'page');
    else item.removeAttribute('aria-current');
  });
}

// Поля поиска дублируются в шапках, поэтому значение берём из state и
// раскладываем по всем полям (включая карточку «Поиск» на главном экране).
function syncSearchInputs() {
  document.querySelectorAll('[data-menu-search-input]').forEach(input => {
    input.value = state.searchQuery;
  });
  $('dashboard-search-input').value = state.searchQuery;
}

function showScreen(name) {
  document.querySelectorAll('.screen').forEach(screen => {
    const isActive = screen.id === `screen-${name}`;
    screen.classList.toggle('active', isActive);
    screen.classList.toggle('hidden', !isActive);
  });
  updateNavActive(name);
  syncSearchInputs();
  window.scrollTo({ top: 0, behavior: 'instant' });
}

// Клик по надписи и значку «Alexandria» в шапке возвращает на главный экран.
function goHome() {
  showScreen('dashboard');
  loadDashboard();
}

function openModal() {
  // Модалка всегда открывается в исходном виде, даже если прошлая загрузка сорвалась.
  resetUploadProgress();
  state.files = { variant: null, answers: null };
  ['variant', 'answers'].forEach(key => {
    $(`zone-${key}`).classList.remove('has-file');
    $(`name-${key}`).textContent = '';
    $(`input-${key}`).value = '';
  });
  $('modal-upload').classList.remove('hidden');
  if (history.state?.modal !== 'upload') {
    history.pushState({ ...history.state, modal: 'upload' }, '');
  }
}

function closeModal(fromHistory = false) {
  // Во время передачи файлов закрываем модалку только через «Отменить загрузку»,
  // иначе XHR продолжит отправку данных в никуда.
  if (isUploading()) return;
  $('modal-upload').classList.add('hidden');
  if (!fromHistory && history.state?.modal === 'upload') {
    history.back();
  }
}

function setupDrop(zoneId, inputId, nameId, key) {
  const zone = $(zoneId);
  const input = $(inputId);
  const name = $(nameId);

  zone.addEventListener('click', event => {
    if (event.target !== input) input.click();
  });
  input.addEventListener('change', () => input.files[0] && pick(input.files[0]));
  zone.addEventListener('dragover', event => {
    event.preventDefault();
    zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', event => {
    event.preventDefault();
    zone.classList.remove('drag-over');
    if (event.dataTransfer.files[0]) pick(event.dataTransfer.files[0]);
  });

  function pick(file) {
    state.files[key] = file;
    name.textContent = file.name;
    zone.classList.add('has-file');
  }
}

// ─── ЗАГРУЗКА С ПРОГРЕССОМ ───────────────────────────────────
// fetch не умеет сообщать о прогрессе отдачи, поэтому файлы варианта
// отправляем через XMLHttpRequest — он даёт события о переданных байтах.
const UPLOAD_TIMEOUT_MS = 180000;
const RING_CIRCUMFERENCE = 326.7; // 2πr при r = 52 — как у кольца на экране результатов

// Ползунок делится на два «бюджета»: передача байтов и разбор документов на
// сервере. Про разбор сервер ничего не сообщает, поэтому до 100% кольцо не
// доходит, пока не придёт ответ: так 100% совпадает с концом загрузки.
const TRANSFER_SHARE = 20;     // сколько процентов кольца отдано передаче файлов
const PROCESS_LINEAR_END = 95; // к этой отметке кольцо доходит к моменту оценки
const PROCESS_CEILING = 99;    // предел, пока сервер не ответил
const PROCESS_ESTIMATE_BASE = 11000;   // базовая оценка разбора, мс (27 заданий)
const PROCESS_ESTIMATE_PER_MB = 3000;  // добавка к оценке за каждый МБ файлов

const uploadProgress = {
  xhr: null,
  rafId: null,
  phase: 'idle',  // idle → upload (передача) → processing (разбор) → done
  percent: 0,     // сглаженный процент для кольца
  target: 0,      // куда стремится кольцо
  loaded: 0,
  total: 0,
  renderedPct: null,
  processingStartedAt: 0,   // начало оценочной фазы обработки
  estimatedProcessingMs: 0, // оценка длительности разбора документов
};

// Отмена загрузки — не ошибка: интерфейс просто возвращается к форме.
class UploadCancelled extends Error {
  constructor() {
    super('Загрузка отменена');
    this.name = 'UploadCancelled';
  }
}

function isUploading() {
  return Boolean(uploadProgress.xhr);
}

// Фаза 1 — передача файлов (процент известен). Фаза 2 — разбор документов
// на сервере: Flask о нём не сообщает, поэтому кольцо заполняется по оценке
// времени (см. updateUploadTarget), а не крутится как индикатор ожидания.
function setUploadPhase(phase) {
  const processing = phase === 'processing';
  $('upload-progress-phase').textContent = processing ? 'Обработка' : 'Загрузка';
  $('upload-progress-note').textContent = processing
    ? 'Файлы переданы. Сервер разбирает документы — это может занять пару минут.'
    : 'Передаём файлы на сервер…';
}

function renderUploadProgress() {
  const p = uploadProgress;
  const pct = Math.round(p.percent);
  if (pct !== p.renderedPct) {
    p.renderedPct = pct;
    $('upload-progress-pct').textContent = `${pct}%`;
    $('upload-progress-bar').setAttribute('aria-valuenow', String(pct));
    $('upload-arc').style.strokeDashoffset = String(RING_CIRCUMFERENCE * (1 - p.percent / 100));
  }
}

// Оценка длительности серверного разбора (pdfplumber + fitz + PIL на 27 заданий).
// Основная работа фиксирована (27 заданий), поэтому база велика, а размер файла
// даёт лишь добавку. От оценки зависит скорость заполнения кольца.
function estimateProcessingMs(bytes) {
  const megabytes = (bytes || 0) / 1048576;
  return Math.min(90000, Math.max(6000, PROCESS_ESTIMATE_BASE + megabytes * PROCESS_ESTIMATE_PER_MB));
}

// Целевой процент кольца для текущей фазы. Передача идёт по реальным байтам
// (их задаёт XHR), обработка — по оценке времени: сначала кольцо заполняется
// равномерно (линейно) до PROCESS_LINEAR_END к моменту оценки, а если разбор
// идёт дольше — мягко дотягивает до PROCESS_CEILING. До 100% дело доходит
// только по ответу сервера, поэтому 100% совпадает с концом загрузки.
function updateUploadTarget(now) {
  const p = uploadProgress;
  if (p.phase === 'done') {
    p.target = 100;
    return;
  }
  if (p.phase !== 'processing') return;

  const elapsed = Math.max(0, now - p.processingStartedAt);
  const estimate = Math.max(1, p.estimatedProcessingMs);

  if (elapsed <= estimate) {
    p.target = TRANSFER_SHARE + (PROCESS_LINEAR_END - TRANSFER_SHARE) * (elapsed / estimate);
  } else {
    const over = (elapsed - estimate) / (estimate * 0.5);
    p.target = PROCESS_LINEAR_END + (PROCESS_CEILING - PROCESS_LINEAR_END) * (1 - Math.exp(-over));
  }
}

// Проценты «догоняют» целевые значения плавно: на localhost передача
// завершается мгновенно, без сглаживания кольцо просто не было бы видно.
function tickUploadProgress() {
  const p = uploadProgress;
  updateUploadTarget(performance.now());
  const diff = p.target - p.percent;
  p.percent = Math.abs(diff) < 0.4 ? p.target : p.percent + diff * 0.18;
  renderUploadProgress();
  p.rafId = requestAnimationFrame(tickUploadProgress);
}

function startUploadProgress(totalBytes) {
  const p = uploadProgress;
  p.phase = 'upload';
  p.percent = 0;
  p.target = 0;
  p.loaded = 0;
  p.total = totalBytes || 0;
  p.renderedPct = null;
  p.processingStartedAt = 0;
  p.estimatedProcessingMs = estimateProcessingMs(p.total);
  $('upload-arc').style.strokeDashoffset = String(RING_CIRCUMFERENCE);
  $('upload-progress-bar').setAttribute('aria-valuenow', '0');
  setUploadPhase('upload');
  renderUploadProgress();
  p.rafId = requestAnimationFrame(tickUploadProgress);
}

// Передача завершилась — переходим к оценочной фазе разбора документов.
function beginProcessingPhase() {
  const p = uploadProgress;
  if (p.phase === 'processing' || p.phase === 'done') return;
  p.phase = 'processing';
  p.processingStartedAt = performance.now();
  setUploadPhase('processing');
}

// Ответ сервера получен: доводим кольцо до 100% и даём его увидеть.
function finishUploadProgress() {
  const p = uploadProgress;
  p.phase = 'done';
  p.target = 100;
  const deadline = performance.now() + 700; // страховка от зависания ожидания
  return new Promise(resolve => {
    const wait = () => {
      if (p.percent >= 99.9 || performance.now() >= deadline) {
        setTimeout(resolve, 250); // короткая пауза, чтобы 100% успели показаться
      } else {
        setTimeout(wait, 40);
      }
    };
    wait();
  });
}

function stopUploadProgress() {
  if (uploadProgress.rafId) cancelAnimationFrame(uploadProgress.rafId);
  uploadProgress.rafId = null;
}

function enterProgressMode() {
  $('upload-title').textContent = 'Загрузка варианта';
  // Крестик закрытия на время передачи убираем: выйти можно только через отмену.
  $('btn-close-upload').classList.add('hidden');
  $('upload-form-body').classList.add('hidden');
  $('upload-form-foot').classList.add('hidden');
  $('upload-progress').classList.remove('hidden');
}

// Возвращает модалку к форме: вызывается и после успеха, и после ошибки, и после отмены.
function resetUploadProgress() {
  const p = uploadProgress;
  stopUploadProgress();
  p.xhr = null;
  p.phase = 'idle';
  p.percent = 0;
  p.target = 0;
  p.loaded = 0;
  p.total = 0;
  p.renderedPct = null;
  p.processingStartedAt = 0;
  p.estimatedProcessingMs = 0;
  $('upload-progress').classList.add('hidden');
  $('upload-progress-bar').classList.remove('is-indeterminate');
  $('upload-progress-bar').setAttribute('aria-valuenow', '0');
  $('upload-arc').style.strokeDashoffset = String(RING_CIRCUMFERENCE);
  $('upload-progress-pct').textContent = '0%';
  $('upload-progress-phase').textContent = 'Загрузка';
  $('upload-progress-note').textContent = 'Передаём файлы на сервер…';
  $('upload-title').textContent = 'Загрузить вариант';
  $('btn-submit-upload').disabled = false;
  $('btn-close-upload').classList.remove('hidden');
  $('upload-form-body').classList.remove('hidden');
  $('upload-form-foot').classList.remove('hidden');
}

function uploadWithProgress(url, form, handlers = {}, ms = UPLOAD_TIMEOUT_MS) {
  return new Promise((resolve, reject) => {
    const p = uploadProgress;
    const xhr = new XMLHttpRequest();
    p.xhr = xhr;
    const release = () => { if (p.xhr === xhr) p.xhr = null; };

    xhr.open('POST', url);
    xhr.timeout = ms;

    xhr.upload.addEventListener('progress', event => {
      if (!event.lengthComputable) return;
      const total = event.total || p.total;
      p.loaded = event.loaded;
      p.total = total;
      // Передаче отдана только часть кольца (TRANSFER_SHARE): 100% покажем лишь
      // по ответу сервера, когда разбор документов уже завершён.
      if (p.phase === 'upload') {
        p.target = total ? Math.min(TRANSFER_SHARE, (event.loaded / total) * TRANSFER_SHARE) : 0;
      }
    });

    // Все байты ушли на сервер, но он ещё парсит PDF/DOCX — точного прогресса нет,
    // поэтому дальше кольцо заполняется по оценке времени (см. updateUploadTarget).
    xhr.upload.addEventListener('load', () => {
      p.loaded = p.total;
      beginProcessingPhase();
      if (handlers.onProcessing) handlers.onProcessing();
    });

    xhr.addEventListener('load', () => {
      release();
      let data = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch { /* сервер вернул не JSON — разберёмся по статусу ответа */ }
      resolve({ ok: xhr.status >= 200 && xhr.status < 300, status: xhr.status, data });
    });
    xhr.addEventListener('error', () => {
      release();
      reject(new Error('Нет соединения. Запустите сервер командой: python server.py'));
    });
    xhr.addEventListener('timeout', () => {
      release();
      reject(new Error(`Сервер не ответил за ${ms / 1000} с. Flask запущен?`));
    });
    xhr.addEventListener('abort', () => {
      release();
      reject(new UploadCancelled());
    });

    // Фолбэк: если события о переданных байтах так и не пришли, всё равно
    // запускаем оценочную фазу, чтобы кольцо не застыло на нуле.
    setTimeout(() => {
      if (p.xhr === xhr && p.loaded === 0) beginProcessingPhase();
    }, 800);

    xhr.send(form);
  });
}

function cancelUpload() {
  if (uploadProgress.xhr) uploadProgress.xhr.abort();
}

async function upload() {
  const { variant, answers } = state.files;
  if (!variant || !answers) {
    alert('Загрузите оба файла: задания и ответы.');
    return;
  }

  const form = new FormData();
  form.append('variant', variant);
  form.append('answers', answers);

  // Пока идёт передача файлов, вместо формы показываем кольцо с процентами.
  $('btn-submit-upload').disabled = true;
  enterProgressMode();
  startUploadProgress(variant.size + answers.size);

  try {
    const res = await uploadWithProgress(`${API}/upload`, form, {
      onProcessing: () => setUploadPhase('processing'),
    });

    if (!res.data) {
      throw new Error(`HTTP ${res.status}. Сервер вернул не JSON. Проверьте консоль Flask.`);
    }
    if (!res.ok) {
      throw new Error((res.data.error || `HTTP ${res.status}`) + (res.data.details ? `\n${res.data.details}` : ''));
    }

    await finishUploadProgress();
    resetUploadProgress();
    closeModal();
    await loadVariants();
  } catch (e) {
    resetUploadProgress();
    if (e.name === 'UploadCancelled') return;
    console.error(e);
    alert(`Ошибка загрузки\n\n${e.message}`);
  }
}

async function loadVariants() {
  try {
    const res = await apiFetch(`${API}/variants`);
    const list = await res.json();
    renderList(list);
  } catch (e) {
    $('variants-grid').innerHTML =
      `<div class="empty-state"><div class="empty-icon">!</div><p>${esc(e.message)}</p></div>`;
  }
}

function renderList(list) {
  const grid = $('variants-grid');
  const query = state.searchQuery.trim().toLowerCase();
  const visibleList = query
    ? list.filter(variant => variant.name.toLowerCase().includes(query) || String(variant.id).includes(query))
    : list;
  grid.querySelectorAll('.variant-card').forEach(card => card.remove());
  const empty = $('empty-state');
  empty.classList.toggle('hidden', visibleList.length > 0);
  if (!visibleList.length) {
    empty.querySelector('p').textContent = query ? 'Ничего не найдено.' : 'Вариантов пока нет.\nЗагрузите первый файл для проверки.';
    return;
  }

  visibleList.forEach(variant => {
    const card = document.createElement('div');
    card.className = 'variant-card';
    card.innerHTML = `
      <div class="vc-name">${esc(variant.name)}</div>
      <div class="vc-meta">
        <span>${esc(variant.date)}</span>
        <span class="vc-badge">${variant.tasks_count} зад.</span>
      </div>
      <div class="vc-actions">
        <button class="btn-solve">Решать</button>
        <button class="btn-delete" title="Удалить" aria-label="Удалить вариант">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
            <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
        </button>
      </div>`;
    card.querySelector('.btn-solve').addEventListener('click', () => startSolver(variant.id, variant.name));
    card.querySelector('.btn-delete').addEventListener('click', () => deleteVariant(variant.id, card));
    grid.appendChild(card);
  });
}

async function loadDashboard() {
  const container = $('recent-variants');
  container.innerHTML = '<p class="dashboard-empty">Загрузка вариантов...</p>';
  try {
    const res = await apiFetch(`${API}/variants`);
    const list = await res.json();
    const recent = list.slice(0, 2);
    if (!recent.length) {
      container.innerHTML = '<p class="dashboard-empty">Новых вариантов пока нет.</p>';
      return;
    }
    container.innerHTML = '';
    recent.forEach(variant => {
      const button = document.createElement('button');
      button.className = 'recent-variant';
      button.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></svg><span class="recent-variant-name">${esc(variant.name)}</span><svg class="action-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>`;
      button.addEventListener('click', () => startSolver(variant.id, variant.name));
      container.appendChild(button);
    });
  } catch (e) {
    container.innerHTML = `<p class="dashboard-empty">${esc(e.message)}</p>`;
  }
}

async function deleteVariant(id, card) {
  if (!confirm('Удалить вариант?')) return;
  try {
    await apiFetch(`${API}/variants/${id}`, { method: 'DELETE' });
    card.remove();
    if (!$('variants-grid').querySelector('.variant-card')) $('empty-state').classList.remove('hidden');
  } catch (e) {
    alert(`Ошибка: ${e.message}`);
  }
}

async function startSolver(variantId, variantName) {
  state.variantId = variantId;
  state.variantName = variantName;
  state.answers = {};

  $('solver-title').textContent = variantName;
  $('tasks-list').innerHTML = '<p class="loading-state">Загрузка...</p>';
  $('results-panel').classList.add('hidden');
  showScreen('solver');

  try {
    const res = await apiFetch(`${API}/variants/${variantId}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    renderTasks(data.tasks);
  } catch (e) {
    $('tasks-list').innerHTML = `<p class="error-state">Ошибка: ${esc(e.message)}</p>`;
  }
}

function renderTasks(tasks) {
  const maxTotal = tasks.reduce((sum, task) => sum + (task.max_points || 0), 0);
  $('solver-progress').textContent = maxTotal > 0
    ? `${tasks.length} заданий · ${maxTotal} первичных баллов`
    : `${tasks.length} заданий`;
  const list = $('tasks-list');
  list.innerHTML = '';
  tasks.forEach(task => list.appendChild(buildCard(task)));
}

function buildCard(task) {
  const card = document.createElement('div');
  card.className = 'task-card';
  card.id = `card-${task.id}`;

  const head = document.createElement('div');
  head.className = 'task-card-head';
  if (task.is_text) {
    const label = task.id === 0 ? 'Текст для заданий 1-3' : 'Текст для заданий 23-26';
    head.innerHTML = `<span class="task-num text-label">${label}</span>`;
  } else {
    const pointsBadge = task.max_points > 1
      ? `<span class="task-points-badge">до ${task.max_points} б.</span>`
      : '';
    head.innerHTML = `<span class="task-num">Задание ${task.id}</span><span class="task-type-badge">${esc(task.type_name || '')}</span>${pointsBadge}`;
  }
  card.appendChild(head);

  const imgArea = document.createElement('div');
  imgArea.className = 'task-img-area';

  const img = document.createElement('img');
  img.className = 'task-img';
  img.alt = `Задание ${task.id}`;
  img.src = `http://127.0.0.1:5000/${task.image_url}`;
  img.onerror = () => {
    imgArea.innerHTML = `<div class="task-text-fallback">${esc(task.text || 'Изображение недоступно')}</div>`;
  };
  imgArea.appendChild(img);

  const canvas = document.createElement('canvas');
  canvas.className = 'task-canvas';
  imgArea.appendChild(canvas);

  const toolbar = makeToolbar(canvas);
  imgArea.appendChild(toolbar);
  card.appendChild(imgArea);

  img.addEventListener('load', () => resizeCanvas(canvas, img));
  window.addEventListener('resize', () => resizeCanvas(canvas, img));
  initDraw(canvas);

  if (!task.is_text) {
    const answerWrap = document.createElement('div');
    answerWrap.className = 'task-answer-wrap';
    answerWrap.innerHTML = `
      <label class="answer-label" for="ans-${task.id}">Ответ${task.max_points > 1 ? ` · до ${task.max_points} б.` : ''}</label>
      <input class="answer-input" id="ans-${task.id}" type="text"
             placeholder="Введите ответ..." autocomplete="off" data-id="${task.id}" />
      <div class="answer-feedback" id="fb-${task.id}"></div>`;
    answerWrap.querySelector('input').addEventListener('input', event => {
      state.answers[String(task.id)] = event.target.value.trim();
    });
    card.appendChild(answerWrap);
  }

  return card;
}

function resizeCanvas(canvas, img) {
  const tmp = canvas.toDataURL();
  canvas.width = img.offsetWidth || img.naturalWidth || 800;
  canvas.height = img.offsetHeight || img.naturalHeight || 400;
  if (tmp !== 'data:,') {
    const restore = new window.Image();
    restore.onload = () => canvas.getContext('2d').drawImage(restore, 0, 0);
    restore.src = tmp;
  }
}

function makeToolbar(canvas) {
  const tb = document.createElement('div');
  tb.className = 'draw-toolbar';

  const colors = ['#ef4444', '#111827', '#2563eb', '#16a34a'];
  canvas._color = colors[0];
  canvas._size = 5;
  canvas._mode = 'pen';

  const toolsLeft = document.createElement('div');
  toolsLeft.className = 'tb-group tb-group-left';
  const toolsRight = document.createElement('div');
  toolsRight.className = 'tb-group tb-group-right';

  colors.forEach(color => {
    const dot = document.createElement('button');
    dot.className = `tb-color${color === canvas._color ? ' active' : ''}`;
    dot.style.background = color;
    dot.title = `Цвет ${color}`;
    dot.setAttribute('aria-label', `Цвет ${color}`);
    dot.addEventListener('click', () => {
      canvas._mode = 'pen';
      canvas._color = color;
      tb.querySelectorAll('.tb-color').forEach(item => item.classList.remove('active'));
      dot.classList.add('active');
      tb.querySelector('.tb-eraser').classList.remove('active');
    });
    toolsLeft.appendChild(dot);
  });

  const sizeWrap = document.createElement('label');
  sizeWrap.className = 'tb-size';
  sizeWrap.title = 'Толщина линии';
  sizeWrap.innerHTML = `
    <span class="tb-size-preview"></span>
    <input class="tb-size-slider" type="range" min="1" max="16" value="${canvas._size}" aria-label="Толщина линии" />
  `;
  const sizePreview = sizeWrap.querySelector('.tb-size-preview');
  const sizeSlider = sizeWrap.querySelector('.tb-size-slider');
  function updateSizePreview() {
    const size = Number(sizeSlider.value);
    canvas._size = size;
    sizePreview.style.height = `${Math.max(2, size)}px`;
  }
  sizeSlider.addEventListener('input', updateSizePreview);
  updateSizePreview();
  toolsLeft.appendChild(sizeWrap);

  const sep = document.createElement('div');
  sep.className = 'tb-sep';

  const eraser = document.createElement('button');
  eraser.className = 'tb-eraser tb-btn tb-icon-btn';
  eraser.textContent = 'Ластик';
  eraser.title = 'Ластик';
  eraser.setAttribute('aria-label', 'Ластик');
  eraser.addEventListener('click', () => {
    canvas._mode = canvas._mode === 'eraser' ? 'pen' : 'eraser';
    eraser.classList.toggle('active', canvas._mode === 'eraser');
  });
  toolsRight.appendChild(eraser);

  const clear = document.createElement('button');
  clear.className = 'tb-btn tb-icon-btn tb-clear';
  clear.textContent = 'Очистить';
  clear.title = 'Очистить';
  clear.setAttribute('aria-label', 'Очистить рисунок');
  clear.addEventListener('click', () => {
    canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
  });
  toolsRight.appendChild(clear);

  tb.appendChild(toolsLeft);
  tb.appendChild(sep);
  tb.appendChild(toolsRight);

  return tb;
}

function initDraw(canvas) {
  const ctx = canvas.getContext('2d');
  let drawing = false;
  let lastX = 0;
  let lastY = 0;

  function pos(event) {
    const rect = canvas.getBoundingClientRect();
    const sx = canvas.width / rect.width;
    const sy = canvas.height / rect.height;
    const source = event.touches ? event.touches[0] : event;
    return [(source.clientX - rect.left) * sx, (source.clientY - rect.top) * sy];
  }

  function start(event) {
    event.preventDefault();
    drawing = true;
    [lastX, lastY] = pos(event);
  }

  function move(event) {
    if (!drawing) return;
    event.preventDefault();
    const [x, y] = pos(event);
    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(x, y);
    if (canvas._mode === 'eraser') {
      ctx.globalCompositeOperation = 'destination-out';
      ctx.lineWidth = canvas._size * 4;
    } else {
      ctx.globalCompositeOperation = 'source-over';
      ctx.strokeStyle = canvas._color;
      ctx.lineWidth = canvas._size;
    }
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();
    [lastX, lastY] = [x, y];
  }

  function stop() {
    drawing = false;
    ctx.globalCompositeOperation = 'source-over';
  }

  canvas.addEventListener('mousedown', start);
  canvas.addEventListener('mousemove', move);
  canvas.addEventListener('mouseup', stop);
  canvas.addEventListener('mouseleave', stop);
  canvas.addEventListener('touchstart', start, { passive: false });
  canvas.addEventListener('touchmove', move, { passive: false });
  canvas.addEventListener('touchend', stop);
}

async function submitAnswers() {
  document.querySelectorAll('.answer-input').forEach(input => {
    state.answers[input.dataset.id] = input.value.trim();
  });

  try {
    const res = await apiFetch(`${API}/variants/${state.variantId}/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers: state.answers }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    markAnswers(data.details);
    showResults(data);
  } catch (e) {
    alert(`Ошибка проверки: ${e.message}`);
  }
}

function markAnswers(details) {
  details.forEach(item => {
    const input = $(`ans-${item.id}`);
    const feedback = $(`fb-${item.id}`);
    if (!input) return;

    const max = item.max_points || 0;
    const full = !item.needs_manual_grading && max > 0 && item.points >= max;
    const partial = !item.needs_manual_grading && !full && item.points > 0;

    input.classList.toggle('correct', full);
    input.classList.toggle('partial', partial);
    input.classList.toggle('wrong', !full && !partial);

    if (item.needs_manual_grading) {
      feedback.className = 'answer-feedback partial';
      feedback.textContent = 'Проверяется вручную (сочинение)';
    } else if (full) {
      feedback.className = 'answer-feedback correct';
      feedback.textContent = max > 1 ? `Верно · ${item.points} из ${max} б.` : 'Верно';
    } else if (partial) {
      feedback.className = 'answer-feedback partial';
      feedback.textContent = `Частично · ${item.points} из ${max} б.`;
    } else {
      feedback.className = 'answer-feedback wrong';
      feedback.textContent = `Правильно: ${item.correct_answer || '?'}`;
    }
  });
}

function showResults(data) {
  $('score-num').textContent = data.score;
  $('score-total').textContent = `/${data.total}`;
  $('score-pct').textContent = `${data.percentage}%`;

  const arc = $('score-arc');
  const circumference = 2 * Math.PI * 52;
  const pct = data.total > 0 ? data.score / data.total : 0;
  arc.style.transition = 'stroke-dashoffset 1s cubic-bezier(.4,0,.2,1)';
  arc.style.strokeDashoffset = circumference * (1 - pct);
  arc.style.stroke = pct >= 0.6 ? 'var(--green)' : 'var(--red)';

  renderParts(data);
  renderDetails(data.details);
  renderEssayForm(data.part2);

  $('results-panel').classList.remove('hidden');
  $('results-panel').scrollIntoView({ behavior: 'smooth' });
}

function renderParts(data) {
  renderPart($('results-parts'), 'Часть 1 · Тест', data.part1);
  renderPart($('results-parts-essay'), 'Часть 2 · Сочинение', data.part2);
}

function renderPart(box, name, part) {
  if (!box) return;
  if (!part || !(part.max > 0)) {
    box.classList.add('hidden');
    box.innerHTML = '';
    return;
  }
  box.classList.remove('hidden');
  box.innerHTML = `
    <div class="results-part">
      <span class="results-part-name">${name}</span>
      <span class="results-part-score">${part.score} / ${part.max}</span>
    </div>`;
}

function renderDetails(details) {
  const box = $('results-details');
  box.innerHTML = '';
  details.forEach(item => {
    const row = document.createElement('div');
    row.className = 'detail-row';

    const max = item.max_points || 0;
    const status = item.needs_manual_grading ? '✎' : item.correct ? '✓' : '×';
    const statusClass = item.needs_manual_grading ? 'manual' : item.correct ? 'ok' : 'bad';

    let answer;
    if (item.needs_manual_grading) {
      answer = '<span style="color:var(--text-muted)">Сочинение — оценивается вручную</span>';
    } else if (item.correct) {
      answer = `<span class="detail-correct">${esc(item.user_answer || '-')}</span>`;
    } else {
      answer = `<span style="color:var(--red)">${esc(item.user_answer || '-')}</span>
        ${item.correct_answer ? `<span style="color:var(--text-muted)"> -> ${esc(item.correct_answer)}</span>` : ''}`;
    }

    const pointsClass = item.needs_manual_grading
      ? 'zero'
      : max > 0 && item.points >= max ? 'full' : item.points > 0 ? 'partial' : 'zero';
    const pointsHtml = item.needs_manual_grading || max > 0
      ? `<span class="detail-points ${pointsClass}">${item.points}/${max}</span>`
      : '';

    row.innerHTML = `
      <span class="detail-num">#${item.id}</span>
      <span class="detail-status ${statusClass}">${status}</span>
      <span class="detail-answer">${answer}</span>
      ${pointsHtml}`;
    box.appendChild(row);
  });
}

function renderEssayForm(part2) {
  const box = $('essay-grade');
  const list = $('essay-criteria');
  const col = $('results-col-essay');
  const grid = $('results-grid');
  const hasEssay = Boolean(part2 && part2.criteria && part2.criteria.length && part2.max > 0);

  if (!hasEssay) {
    box.classList.add('hidden');
    col.classList.add('hidden');
    grid.classList.remove('has-essay');
    list.innerHTML = '';
    return;
  }

  const values = part2.values || {};
  list.innerHTML = part2.criteria.map(crit => {
    const value = Number(values[crit.id] ?? 0);
    return `
      <label class="essay-criterion">
        <span class="essay-criterion-name">${esc(crit.id)}. ${esc(crit.name)}</span>
        <span class="essay-criterion-input">
          <input class="essay-input" type="number" min="0" max="${crit.max}" step="1"
                 value="${value}" data-criterion="${esc(crit.id)}" aria-label="${esc(crit.name)}" />
          <span class="essay-criterion-max">/${crit.max}</span>
        </span>
      </label>`;
  }).join('');

  list.querySelectorAll('.essay-input').forEach(input => {
    input.addEventListener('input', updateEssayTotal);
  });

  $('btn-save-essay').textContent = part2.pending
    ? 'Сохранить оценку сочинения'
    : 'Обновить оценку сочинения';

  col.classList.remove('hidden');
  grid.classList.add('has-essay');
  box.classList.remove('hidden');
  updateEssayTotal();
}

function updateEssayTotal() {
  const inputs = document.querySelectorAll('.essay-input');
  if (!inputs.length) return;
  let total = 0;
  let max = 0;
  inputs.forEach(input => {
    total += Number(input.value) || 0;
    max += Number(input.max) || 0;
  });
  const target = $('essay-total');
  if (target) target.textContent = `Итого: ${total} / ${max}`;
}

async function submitEssayGrade() {
  const criteria = {};
  document.querySelectorAll('.essay-input').forEach(input => {
    criteria[input.dataset.criterion] = Number(input.value) || 0;
  });

  const btn = $('btn-save-essay');
  btn.disabled = true;
  try {
    const res = await apiFetch(`${API}/variants/${state.variantId}/essay-grade`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ criteria }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    showResults(data);
  } catch (e) {
    alert(`Ошибка сохранения оценки: ${e.message}`);
  } finally {
    btn.disabled = false;
  }
}

function esc(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

const THEME_KEY = 'alexandria-theme';

function currentTheme() {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
}

function applyTheme(theme) {
  const isDark = theme === 'dark';
  document.documentElement.dataset.theme = isDark ? 'dark' : 'light';
  document.querySelectorAll('[data-theme-toggle]').forEach(button => {
    button.setAttribute('aria-pressed', String(isDark));
    button.setAttribute('aria-label', isDark ? 'Включить светлую тему' : 'Включить тёмную тему');
    button.title = isDark ? 'Светлая тема' : 'Тёмная тема';
  });
}

function toggleTheme() {
  const next = currentTheme() === 'dark' ? 'light' : 'dark';
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch (e) { /* приватный режим — тема живёт до перезагрузки */ }
  applyTheme(next);
}

function initTheme() {
  applyTheme(currentTheme());
  document.querySelectorAll('[data-theme-toggle]').forEach(button => {
    button.addEventListener('click', toggleTheme);
  });
}

function renderActivity() {
  const months = ['Сен', 'Окт', 'Ноя', 'Дек', 'Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг'];
  const target = $('activity-months');
  if (!target || target.children.length) return;
  target.innerHTML = months.map((month, monthIndex) => {
    const cells = Array.from({ length: 20 }, (_, day) => {
      const seed = (monthIndex * 11 + day * 7 + 3) % 10;
      const level = seed > 7 ? 3 : seed > 4 ? 2 : seed > 2 ? 1 : 0;
      return `<i${level ? ` class="level-${level}"` : ''}></i>`;
    }).join('');
    return `<div class="activity-month"><b>${month}</b>${cells}</div>`;
  }).join('');
}

document.addEventListener('DOMContentLoaded', () => {
  initTheme();

  function enterApp() {
    showScreen('list');
    loadVariants();
  }

  // Профиль открывается с построением диаграмм активности — так же, как с главного экрана.
  function goProfile() {
    renderActivity();
    showScreen('profile');
  }

  // Поиск из шапки и из карточки на главном экране работает одинаково:
  // запоминаем запрос, раскладываем его по всем полям и уходим в список вариантов.
  function runSearch(value) {
    state.searchQuery = value;
    syncSearchInputs();
    enterApp();
  }

  $('btn-auth-login').addEventListener('click', enterApp);
  $('btn-auth-register').addEventListener('click', enterApp);
  $('btn-open-all').addEventListener('click', enterApp);
  $('btn-dashboard-create').addEventListener('click', openModal);
  $('btn-dashboard-profile').addEventListener('click', goProfile);
  document.querySelectorAll('[data-home]').forEach(logo => {
    logo.addEventListener('click', goHome);
  });
  // Пункты меню в шапке: «Варианты» открывает список, «Профиль» — профиль.
  const navActions = { variants: enterApp, profile: goProfile };
  document.querySelectorAll('[data-nav]').forEach(item => {
    const action = navActions[item.dataset.nav];
    if (action) item.addEventListener('click', action);
  });
  $('dashboard-search-form').addEventListener('submit', event => {
    event.preventDefault();
    runSearch($('dashboard-search-input').value);
  });
  // Поиск в шапке: Enter в поле или клик по лупе уводят в список вариантов с фильтром.
  document.querySelectorAll('[data-menu-search]').forEach(form => {
    form.addEventListener('submit', event => {
      event.preventDefault();
      const input = form.querySelector('[data-menu-search-input]');
      runSearch(input ? input.value : '');
    });
  });
  $('btn-open-upload').addEventListener('click', openModal);
  $('btn-close-upload').addEventListener('click', closeModal);
  $('btn-cancel-upload').addEventListener('click', closeModal);
  $('modal-upload').addEventListener('click', event => {
    if (event.target === $('modal-upload')) closeModal();
  });
  window.addEventListener('popstate', () => {
    if (isUploadModalOpen() && !isUploading()) closeModal(true);
  });

  setupDrop('zone-variant', 'input-variant', 'name-variant', 'variant');
  setupDrop('zone-answers', 'input-answers', 'name-answers', 'answers');

  $('btn-submit-upload').addEventListener('click', upload);
  $('btn-cancel-progress').addEventListener('click', cancelUpload);
  $('btn-back').addEventListener('click', () => {
    showScreen('list');
    loadVariants();
  });
  $('btn-submit-answers').addEventListener('click', submitAnswers);
  $('btn-save-essay').addEventListener('click', submitEssayGrade);
  $('btn-results-back').addEventListener('click', () => {
    $('results-panel').classList.add('hidden');
    showScreen('list');
    loadVariants();
  });

  showScreen('dashboard');
  loadDashboard();
});
