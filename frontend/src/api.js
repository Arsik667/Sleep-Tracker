// Обёртки над API. Адрес бэкенда задаётся при сборке через REACT_APP_API_URL:
// пустая строка — тот же origin (в Docker nginx проксирует /api на бэкенд),
// переменная не задана — локальный uvicorn на :8000.
const API_URL = process.env.REACT_APP_API_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : `Ошибка API (${status})`);
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
    throw new ApiError(0, 'Сервер не отвечает. Запущен ли бэкенд?');
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(response.status, body?.detail ?? response.statusText);
  }
  return body;
}

export function checkSleep(night, save) {
  return request(`/api/sleep-check?save=${save ? 'true' : 'false'}`, {
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

// Ошибки валидации FastAPI (422) → { fields: {имя_поля: текст}, general: [текст] }.
// Ошибки отдельных полей Pydantic пишет по-английски — переводим частые типы,
// а тексты наших проверок (связи между полями) уже на русском.
export function validationMessages(detail) {
  const fields = {};
  const general = [];
  for (const error of Array.isArray(detail) ? detail : []) {
    const loc = error.loc ?? [];
    const message = humanize(error);
    if (loc[0] === 'body' && loc.length > 1) {
      fields[loc[loc.length - 1]] = message;
    } else {
      general.push(message);
    }
  }
  return { fields, general };
}

function humanize({ type, msg, ctx = {} }) {
  switch (type) {
    case 'greater_than_equal':
      return `Не меньше ${ctx.ge}`;
    case 'less_than_equal':
      return `Не больше ${ctx.le}`;
    case 'greater_than':
      return `Должно быть больше ${ctx.gt}`;
    case 'int_parsing':
    case 'float_parsing':
      return 'Нужно число';
    case 'int_from_float':
      return 'Нужно целое число';
    case 'time_parsing':
    case 'time_type':
      return 'Неверное время';
    case 'date_parsing':
    case 'date_from_datetime_parsing':
      return 'Неверная дата';
    case 'missing':
      return 'Обязательное поле';
    default:
      return String(msg).replace(/^Value error, /, '');
  }
}

// Сегодняшняя дата по часам пользователя в формате YYYY-MM-DD
// (toISOString дал бы дату по UTC — ночью это может быть «вчера»).
export function localToday() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
