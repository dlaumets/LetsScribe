const API_KEY_STORAGE = 'transcribe_api_key';

const MEDIA_EXTENSIONS = new Set([
  'ogg', 'opus', 'mp3', 'm4a', 'wav', 'webm', 'aac', 'flac', 'mpeg', 'mp4', 'oga',
  'mov', 'mkv', 'avi', 'mpg', '3gp',
]);

const STAGE_LABELS = {
  pending: 'В очереди',
  queued: 'В очереди',
  processing: 'Обработка',
  loading_model: 'Загрузка модели',
  preparing: 'Подготовка аудио',
  transcribing: 'Распознавание речи',
  finishing: 'Завершение',
  done: 'Готово',
  completed: 'Готово',
  failed: 'Ошибка',
};

export function getApiKey() {
  return localStorage.getItem(API_KEY_STORAGE) || '';
}

export function hasApiKey() {
  return Boolean(getApiKey().trim());
}

export function setApiKey(key) {
  localStorage.setItem(API_KEY_STORAGE, key.trim());
}

export function apiHeaders() {
  const key = getApiKey();
  if (!key) throw new Error('Нужен API-ключ — нажмите «Получить ключ» в боковой панели');
  return { 'X-API-Key': key };
}

export function formatFileSize(bytes) {
  if (bytes == null || Number.isNaN(bytes)) return '';
  if (bytes < 1024) return `${bytes} B`;
  const mb = bytes / 1024 / 1024;
  if (mb < 0.1) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${mb.toFixed(2)} MB`;
}

export function isAudioFile(file) {
  return isMediaFile(file);
}

export function isMediaFile(file) {
  if (!file) return false;
  const type = file.type || '';
  if (type.startsWith('audio/') || type.startsWith('video/')) return true;
  const ext = file.name.split('.').pop()?.toLowerCase();
  return ext ? MEDIA_EXTENSIONS.has(ext) : false;
}

export function friendlyApiError(res, data) {
  const detail = typeof data?.detail === 'string' ? data.detail : null;
  if (detail) return detail;
  switch (res.status) {
    case 400: return 'Неверный запрос — проверьте файл и настройки';
    case 401: return 'Неверный API-ключ — получите новый или вставьте свой';
    case 403: return 'Доступ запрещён';
    case 404: return 'Не найдено';
    case 413: return 'Файл слишком большой';
    case 429: return 'Слишком много запросов — подождите и попробуйте снова';
    case 500:
    case 502:
    case 503: return 'Сервер временно недоступен — попробуйте позже';
    default: return res.ok ? '' : `Ошибка ${res.status}`;
  }
}

export async function copyToClipboard(text) {
  if (!text) return false;
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  }
}

export function setStatus(el, message, type = '') {
  if (!el) return;
  el.textContent = message;
  el.className = type ? `status ${type}` : 'status';
  if (message) el.setAttribute('role', 'status');
}

export function setButtonLoading(btn, loading, loadingLabel) {
  if (!btn) return;
  if (loading) {
    if (!btn.dataset.label) btn.dataset.label = btn.textContent;
    btn.disabled = true;
    btn.classList.add('is-loading');
    if (loadingLabel) btn.textContent = loadingLabel;
  } else {
    btn.disabled = false;
    btn.classList.remove('is-loading');
    if (btn.dataset.label) btn.textContent = btn.dataset.label;
  }
}

export function stageLabel(stage) {
  return STAGE_LABELS[stage] || stage || 'Обработка';
}

export function formatDuration(seconds) {
  if (seconds == null) return '';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m > 0 ? `${m} мин ${s} с` : `${s} с`;
}

export function formatMeta(meta = {}, extra = {}) {
  return [
    meta.preset && `пресет ${meta.preset}`,
    meta.language && meta.language,
    meta.duration != null && formatDuration(meta.duration),
    meta.processing_time_ms && `${(meta.processing_time_ms / 1000).toFixed(1)} с обработки`,
    extra.saved === false && 'не сохранено',
  ].filter(Boolean).join(' · ');
}

export function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export class JobCancelledError extends Error {
  constructor(message = 'Распознавание отменено') {
    super(message);
    this.name = 'JobCancelledError';
  }
}

function throwIfAborted(signal) {
  if (signal?.aborted) throw new JobCancelledError();
}

function delay(ms, signal) {
  throwIfAborted(signal);
  return new Promise((resolve, reject) => {
    const id = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(id);
      reject(new JobCancelledError());
    }
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

function wrapFetchError(e, signal) {
  if (signal?.aborted || e?.name === 'AbortError') throw new JobCancelledError();
  if (e instanceof TypeError) throw new Error('Нет соединения с сервером — проверьте сеть');
  throw e;
}

export async function pollJob(jobId, { onProgress, intervalMs = 800, signal } = {}) {
  let delayMs = intervalMs;
  while (true) {
    throwIfAborted(signal);
    let res;
    let data;
    try {
      res = await fetch(`/v1/jobs/${jobId}`, { headers: apiHeaders(), signal });
      data = await res.json();
    } catch (e) {
      wrapFetchError(e, signal);
    }
    if (!res.ok) throw new Error(friendlyApiError(res, data) || 'Ошибка опроса задачи');

    if (onProgress) onProgress(data);

    if (data.status === 'completed') return data;
    if (data.status === 'cancelled') throw new JobCancelledError(data.error || 'Распознавание отменено');
    if (data.status === 'failed') throw new Error(data.error || 'Транскрипция не удалась');

    await delay(delayMs, signal);
    delayMs = Math.min(delayMs * 1.15, 3000);
  }
}

export async function submitJob(formData, { signal } = {}) {
  let res;
  let data;
  try {
    res = await fetch('/v1/jobs', {
      method: 'POST',
      headers: apiHeaders(),
      body: formData,
      signal,
    });
    data = await res.json();
  } catch (e) {
    wrapFetchError(e, signal);
  }
  if (!res.ok) throw new Error(friendlyApiError(res, data) || 'Ошибка отправки');
  return data;
}

export async function cancelJob(jobId, { signal } = {}) {
  let res;
  let data;
  try {
    res = await fetch(`/v1/jobs/${jobId}`, {
      method: 'DELETE',
      headers: apiHeaders(),
      signal,
    });
    data = await res.json();
  } catch (e) {
    wrapFetchError(e, signal);
  }
  if (res.status === 404) throw new Error('Задача не найдена');
  if (res.status === 409) throw new JobCancelledError('Распознавание уже завершено');
  if (!res.ok) throw new Error(friendlyApiError(res, data) || 'Не удалось отменить задачу');
  return data;
}

export async function registerKey() {
  const res = await fetch('/v1/register', { method: 'POST' });
  const data = await res.json();
  if (!res.ok) throw new Error(friendlyApiError(res, data) || 'Не удалось создать ключ');
  setApiKey(data.api_key);
  return data.api_key;
}

export function bindApiKeyInput(inputId, statusId, registerBtnId) {
  const input = document.getElementById(inputId);
  const saved = getApiKey();
  if (saved) input.value = saved;

  input.addEventListener('change', () => setApiKey(input.value));
  input.addEventListener('input', () => {
    if (input.value.trim()) setApiKey(input.value);
    updateAuthToggleState();
  });

  if (registerBtnId) {
    const registerBtn = document.getElementById(registerBtnId);
    registerBtn.addEventListener('click', async () => {
      const status = document.getElementById(statusId);
      setStatus(status, 'Создаём ключ…');
      setButtonLoading(registerBtn, true, 'Создаём…');
      try {
        const key = await registerKey();
        input.value = key;
        setStatus(status, 'Ключ сохранён в браузере', 'ok');
        input.dispatchEvent(new Event('apikeychange', { bubbles: true }));
        updateAuthToggleState();
      } catch (e) {
        setStatus(status, e.message, 'error');
      } finally {
        setButtonLoading(registerBtn, false);
      }
    });
  }
}

const DESKTOP_MQ = '(min-width: 1024px)';

function isDesktopLayout() {
  return window.matchMedia(DESKTOP_MQ).matches;
}

function updateAuthToggleState() {
  const toggle = document.getElementById('auth-toggle');
  if (!toggle) return;
  toggle.classList.toggle('has-key', hasApiKey());
}

export function openAuthPanel(panelId = 'sidebar-auth') {
  if (isDesktopLayout()) return;
  const panel = document.getElementById(panelId);
  const toggle = document.getElementById('auth-toggle');
  panel?.classList.add('is-open');
  toggle?.setAttribute('aria-expanded', 'true');
}

export function bindAuthToggle(toggleId = 'auth-toggle', panelId = 'sidebar-auth') {
  const toggle = document.getElementById(toggleId);
  const panel = document.getElementById(panelId);
  if (!toggle || !panel) return;

  const mq = window.matchMedia(DESKTOP_MQ);

  function setOpen(open) {
    if (mq.matches) {
      panel.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
      return;
    }
    panel.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
  }

  toggle.addEventListener('click', () => {
    setOpen(!panel.classList.contains('is-open'));
  });

  mq.addEventListener('change', () => {
    if (mq.matches) setOpen(false);
    else if (!hasApiKey()) setOpen(true);
  });

  if (!mq.matches && !hasApiKey()) setOpen(true);
  updateAuthToggleState();
}

export function createProgressController(panelId) {
  const panel = document.getElementById(panelId);
  const container = panel?.closest('.result-panel') || document;
  const fill = container.querySelector('.progress-fill');
  const pctEl = panel?.querySelector('.progress-pct');
  const stageEls = container.querySelectorAll('.progress-stage');
  const previewEl = panel?.querySelector('.preview-text');

  return {
    show() { panel?.classList.add('active'); },
    hide() { panel?.classList.remove('active'); },
    update(data) {
      const pct = Math.round(data.progress_percent || 0);
      const stage = stageLabel(data.progress_stage || data.status);
      if (fill) fill.style.width = `${pct}%`;
      if (pctEl) pctEl.textContent = `${pct}%`;
      stageEls.forEach((el) => { el.textContent = stage; });
      if (previewEl) previewEl.textContent = data.partial_text || '';
    },
  };
}
