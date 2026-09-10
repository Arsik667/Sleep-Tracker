// Подписи для значений, которые API отдаёт в виде ключей.

export const CATEGORY = {
  excellent: { label: 'Отлично', icon: '✓', status: 'good' },
  good: { label: 'Хорошо', icon: '✓', status: 'good' },
  fair: { label: 'Средне', icon: '!', status: 'warning' },
  poor: { label: 'Плохо', icon: '✕', status: 'critical' },
};

export const COMPONENT = {
  duration: 'Длительность',
  efficiency: 'Эффективность',
  continuity: 'Непрерывность',
  stages: 'Стадии сна',
  consistency: 'Регулярность',
};

export const COMPONENT_HINT = {
  duration: 'оптимум 7–9 ч',
  efficiency: 'сон / время в постели',
  continuity: 'WASO и пробуждения',
  stages: 'доля глубокого и REM',
  consistency: 'разброс отбоя за 7 ночей',
};

export const MISSING_REASON = {
  stages: 'не указаны',
  consistency: 'нужно ≥ 2 прошлых ночей',
};

export const PENALTY = {
  caffeine_after_14: 'Кофеин после 14:00',
  screen_before_bed: 'Экран перед сном',
};

// Совет относится к компоненту, штрафу или ни к чему конкретному.
// Для штрафов название уже стоит в начале текста совета — метка просто «Штраф».
export const TIP_TAG = { ...COMPONENT, caffeine_after_14: 'Штраф', screen_before_bed: 'Штраф', general: 'Общее' };

export function formatHours(hours) {
  const total = Math.round(hours * 60);
  const h = Math.floor(total / 60);
  const m = total % 60;
  return m ? `${h} ч ${m} мин` : `${h} ч`;
}

export function formatDate(iso, options = { day: 'numeric', month: 'long' }) {
  // Полдень, чтобы часовой пояс не сдвинул дату на соседний день.
  return new Date(`${iso}T12:00:00`).toLocaleDateString('ru-RU', options);
}
