// Обёртки над API. Адрес бэкенда задаётся при сборке через REACT_APP_API_URL:
// пустая строка — тот же origin (в Docker nginx проксирует /api на бэкенд),
// переменная не задана — локальный uvicorn на :8000.
const API_URL = process.env.REACT_APP_API_URL ?? 'http://localhost:8000';

// status 0 — сервер не ответил вовсе. Текст ошибки для человека выбирает интерфейс
// (на своём языке) по status и detail — см. errorMessage().
export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : `API error (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
  } catch {
    throw new ApiError(0, null);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(response.status, body?.detail ?? null);
  }
  return body;
}

export function checkSleep(night, save, lang) {
  return request(`/api/sleep-check?save=${save ? 'true' : 'false'}&lang=${lang}`, {
    method: 'POST',
    body: JSON.stringify(night),
  });
}

export function fetchHistory(limit = 30) {
  return request(`/api/history?limit=${limit}`);
}

export function fetchSummary(asOf) {
  return request(`/api/history/summary?as_of=${asOf}`);
}

export function errorMessage(error, t) {
  if (error.status === 0) return t.errors.network;
  if (typeof error.detail === 'string' && error.status < 500) return error.detail;
  return t.errors.unknown(error.status);
}

// Ошибки валидации FastAPI (422) → { fields: {имя_поля: текст}, general: [текст] }.
// Текст берём из словаря по коду ошибки (type); незнакомый код — показываем msg как есть.
export function validationMessages(detail, t) {
  const fields = {};
  const general = [];
  for (const error of Array.isArray(detail) ? detail : []) {
    const loc = error.loc ?? [];
    const translate = t.errors.validation[error.type];
    const message = translate ? translate(error.ctx ?? {}) : String(error.msg).replace(/^Value error, /, '');
    if (loc[0] === 'body' && loc.length > 1) {
      fields[loc[loc.length - 1]] = message;
    } else {
      general.push(message);
    }
  }
  return { fields, general };
}

// Сегодняшняя дата по часам пользователя в формате YYYY-MM-DD
// (toISOString дал бы дату по UTC — ночью это может быть «вчера»).
export function localToday() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
