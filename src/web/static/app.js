const API_KEY_STORAGE = 'transcribe_api_key';

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

export function setApiKey(key) {
  localStorage.setItem(API_KEY_STORAGE, key.trim());
}

export function apiHeaders() {
  const key = getApiKey();
  if (!key) throw new Error('Нужен API key — нажмите «Получить ключ»');
  return { 'X-API-Key': key };
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

export async function pollJob(jobId, { onProgress, intervalMs = 800 } = {}) {
  let delay = intervalMs;
  while (true) {
    const res = await fetch(`/v1/jobs/${jobId}`, { headers: apiHeaders() });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Ошибка опроса задачи');

    if (onProgress) onProgress(data);

    if (data.status === 'completed') return data;
    if (data.status === 'failed') throw new Error(data.error || 'Транскрипция не удалась');

    await new Promise((r) => setTimeout(r, delay));
    delay = Math.min(delay * 1.15, 3000);
  }
}

export async function submitJob(formData) {
  const res = await fetch('/v1/jobs', {
    method: 'POST',
    headers: apiHeaders(),
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Ошибка отправки');
  return data;
}

export async function registerKey() {
  const res = await fetch('/v1/register', { method: 'POST' });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Не удалось создать ключ');
  setApiKey(data.api_key);
  return data.api_key;
}

export function bindApiKeyInput(inputId, statusId, registerBtnId) {
  const input = document.getElementById(inputId);
  const saved = getApiKey();
  if (saved) input.value = saved;

  input.addEventListener('change', () => setApiKey(input.value));

  if (registerBtnId) {
    document.getElementById(registerBtnId).addEventListener('click', async () => {
      const status = document.getElementById(statusId);
      status.textContent = 'Создаём ключ...';
      status.className = 'status';
      try {
        const key = await registerKey();
        input.value = key;
        status.textContent = 'Ключ сохранён в браузере';
        status.className = 'status ok';
      } catch (e) {
        status.textContent = e.message;
        status.className = 'status error';
      }
    });
  }
}

export function createProgressController(panelId) {
  const panel = document.getElementById(panelId);
  const fill = panel?.querySelector('.progress-fill');
  const pctEl = panel?.querySelector('.progress-pct');
  const stageEl = panel?.querySelector('.progress-stage');
  const previewEl = panel?.querySelector('.preview-text');

  return {
    show() { panel?.classList.add('active'); },
    hide() { panel?.classList.remove('active'); },
    update(data) {
      const pct = Math.round(data.progress_percent || 0);
      if (fill) fill.style.width = `${pct}%`;
      if (pctEl) pctEl.textContent = `${pct}%`;
      if (stageEl) stageEl.textContent = stageLabel(data.progress_stage || data.status);
      if (previewEl) previewEl.textContent = data.partial_text || '';
    },
  };
}
