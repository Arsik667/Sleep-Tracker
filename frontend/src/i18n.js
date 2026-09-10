// Тексты интерфейса на двух языках. У ru и en одинаковые ключи; строки с параметрами — функции.
// Советы приходят с бэкенда уже на нужном языке (?lang=…), ошибки 422 — с кодом в поле type.
import { createContext, useContext } from 'react';

export const LANGUAGES = ['ru', 'en'];
const STORAGE_KEY = 'sleeptrack-lang';

const ru = {
  locale: 'ru-RU',
  units: { h: 'ч', min: 'мин' },
  app: {
    tagline: 'Оценка качества сна за ночь, советы по слабым местам и тренд по истории.',
    footer: 'SleepTrack — учебный проект, а не медицинский инструмент. Если сон плохой неделями, стоит обратиться к врачу.',
    language: 'Язык интерфейса',
  },
  category: { excellent: 'Отлично', good: 'Хорошо', fair: 'Средне', poor: 'Плохо' },
  component: {
    duration: 'Длительность',
    efficiency: 'Эффективность',
    continuity: 'Непрерывность',
    stages: 'Стадии сна',
    consistency: 'Регулярность',
  },
  componentHint: {
    duration: 'оптимум 7–9 ч',
    efficiency: 'сон / время в постели',
    continuity: 'WASO и пробуждения',
    stages: 'доля глубокого и REM',
    consistency: 'разброс отбоя за 7 ночей',
  },
  missingReason: { stages: 'не указаны', consistency: 'нужно ≥ 2 прошлых ночей' },
  penalty: { caffeine_after_14: 'Кофеин после 14:00', screen_before_bed: 'Экран перед сном' },
  // Для штрафов название уже стоит в начале текста совета — метка просто «Штраф».
  tipTag: { penalty: 'Штраф', general: 'Общее' },
  form: {
    title: 'Как прошла ночь',
    schedule: 'Режим',
    date: 'Дата (утро)',
    sleepHours: 'Сон, часов',
    sleepHint: '7.5 = 7 ч 30 мин',
    sleepExceedsBed: 'Больше, чем времени в постели',
    bedtime: 'Отбой',
    wake: 'Подъём',
    inBed: (duration) => `В постели ${duration}`,
    awake: 'Пробуждения',
    waso: 'Без сна ночью, мин',
    wasoHint: 'WASO — после засыпания',
    awakenings: 'Пробуждений',
    stages: 'Стадии сна',
    stagesNote: '— если есть трекер',
    deep: 'Глубокий, мин',
    rem: 'REM, мин',
    unknown: 'не знаю',
    evening: 'Вечер перед сном',
    caffeine: 'Кофеин после 14:00',
    screen: 'Экран в последний час перед сном',
    save: 'Сохранить в историю',
    submit: 'Оценить сон',
    submitting: 'Считаю…',
  },
  result: {
    emptyTitle: 'Оценка появится здесь',
    emptyText:
      'Заполните форму и нажмите «Оценить сон». Итог 0–100 складывается из пяти компонентов, а кофеин и экран перед сном снимают баллы.',
    nightOf: (date) => `Ночь на ${date}`,
    saved: 'сохранено в историю',
    replaced: 'сохранено, прошлая запись за эту дату заменена',
    notSaved: 'не сохранено',
    meter: 'Оценка сна',
    cap: (cap) => `Оценка ограничена ${cap} баллами: при таком коротком сне выше не бывает.`,
    inBed: 'В постели',
    efficiency: 'Эффективность',
    efficiencySub: 'сон / время в постели',
    debt: 'Недосып за ночь',
    debtNone: 'нет',
    debtSub: 'от нормы 8 ч',
    spread: 'Разброс отбоя',
    spreadNone: 'мало истории',
    spreadSub: (nights) => `по ${nights} ночам`,
    breakdown: 'Из чего сложилась оценка',
    weight: 'вес',
    missing: (reason) => `нет данных — ${reason}, вес разделён между остальными`,
    penalties: 'Штрафы:',
    tips: 'Что можно улучшить',
  },
  history: {
    title: 'История и тренд',
    subtitle: (n) => `Последние ${n} сохранённых ночей`,
    view: 'Вид истории',
    chart: 'График',
    table: 'Таблица',
    loading: 'Загружаю историю…',
    unavailable: 'История недоступна: база данных не отвечает. Оценка сна при этом работает — без регулярности режима.',
    empty: 'Пока нет сохранённых ночей. Оценивайте сон с включённым «Сохранить в историю» — здесь появится график с трендом.',
    avg7: 'Средний балл · 7 дней',
    avg30: 'Средний балл · 30 дней',
    nights: (n) => `по ${n} ноч.`,
    trend: 'Тренд',
    trendSub: (prev) => `к прошлой неделе (${prev})`,
    trendNone: 'нужны записи за 2 недели',
    debtWeek: 'Недосып за неделю',
    debtNone: 'нет',
    debtSub: (norm) => `от нормы ${norm} ч за ночь`,
    legendNight: 'балл за ночь',
    legendAvg: 'среднее за 7 дней',
    caption: 'Линии сетки — границы категорий: от 50 «средне», от 70 «хорошо», от 85 «отлично».',
    chartLabel: (n) => `График оценки сна за ${n} ноч. Стрелки влево и вправо — перемещение по ночам.`,
    tipSleep: 'сон',
    columns: {
      date: 'Дата',
      times: 'Отбой — подъём',
      sleep: 'Сон',
      waso: 'WASO',
      awakenings: 'Пробужд.',
      score: 'Балл',
      category: 'Категория',
    },
  },
  errors: {
    network: 'Сервер не отвечает. Запущен ли бэкенд?',
    saveUnavailable: 'База данных недоступна — сохранить ночь не получилось. Снимите «Сохранить в историю» или попробуйте позже.',
    unknown: (status) => `Ошибка API (${status})`,
    // Коды ошибок 422: частые типы Pydantic и наши проверки из core.NightData.
    validation: {
      greater_than_equal: ({ ge }) => `Не меньше ${ge}`,
      less_than_equal: ({ le }) => `Не больше ${le}`,
      greater_than: ({ gt }) => `Должно быть больше ${gt}`,
      int_parsing: () => 'Нужно число',
      float_parsing: () => 'Нужно число',
      int_from_float: () => 'Нужно целое число',
      time_parsing: () => 'Неверное время',
      time_type: () => 'Неверное время',
      date_parsing: () => 'Неверная дата',
      date_from_datetime_parsing: () => 'Неверная дата',
      missing: () => 'Обязательное поле',
      date_in_future: () => 'Дата ночи не может быть в будущем',
      same_bed_and_wake: () => 'Время отбоя и подъёма совпадают',
      sleep_exceeds_bed: ({ sleep_hours: s, in_bed_hours: b }) => `Сна ${s} ч — больше, чем времени в постели (${b} ч)`,
      waso_exceeds_bed: () => 'Сон вместе с WASO не помещается во время в постели',
      stages_exceed_sleep: () => 'Глубокий и REM-сон вместе больше общего времени сна',
    },
  },
};

const en = {
  locale: 'en-US',
  units: { h: 'h', min: 'min' },
  app: {
    tagline: 'Sleep quality score for a night, tips for the weak spots and a trend over your history.',
    footer: 'SleepTrack is a learning project, not a medical tool. If you sleep badly for weeks, consider seeing a doctor.',
    language: 'Interface language',
  },
  category: { excellent: 'Excellent', good: 'Good', fair: 'Fair', poor: 'Poor' },
  component: {
    duration: 'Duration',
    efficiency: 'Efficiency',
    continuity: 'Continuity',
    stages: 'Sleep stages',
    consistency: 'Consistency',
  },
  componentHint: {
    duration: 'optimum 7–9 h',
    efficiency: 'sleep / time in bed',
    continuity: 'WASO and awakenings',
    stages: 'deep and REM share',
    consistency: 'bedtime spread over 7 nights',
  },
  missingReason: { stages: 'not provided', consistency: 'needs ≥ 2 previous nights' },
  penalty: { caffeine_after_14: 'Caffeine after 2 pm', screen_before_bed: 'Screen before bed' },
  tipTag: { penalty: 'Penalty', general: 'General' },
  form: {
    title: 'How was your night',
    schedule: 'Schedule',
    date: 'Date (morning)',
    sleepHours: 'Sleep, hours',
    sleepHint: '7.5 = 7 h 30 min',
    sleepExceedsBed: 'Longer than time in bed',
    bedtime: 'Bedtime',
    wake: 'Wake-up',
    inBed: (duration) => `In bed ${duration}`,
    awake: 'Awakenings',
    waso: 'Awake at night, min',
    wasoHint: 'WASO — after falling asleep',
    awakenings: 'Awakenings',
    stages: 'Sleep stages',
    stagesNote: '— if you have a tracker',
    deep: 'Deep, min',
    rem: 'REM, min',
    unknown: 'unknown',
    evening: 'Before bed',
    caffeine: 'Caffeine after 2 pm',
    screen: 'Screen in the last hour before bed',
    save: 'Save to history',
    submit: 'Score my sleep',
    submitting: 'Scoring…',
  },
  result: {
    emptyTitle: 'Your score will appear here',
    emptyText:
      'Fill in the form and press “Score my sleep”. The 0–100 total combines five components; caffeine and screens before bed take points off.',
    nightOf: (date) => `Night of ${date}`,
    saved: 'saved to history',
    replaced: 'saved, replacing the earlier record for this date',
    notSaved: 'not saved',
    meter: 'Sleep score',
    cap: (cap) => `The score is capped at ${cap}: with sleep this short it can't go higher.`,
    inBed: 'Time in bed',
    efficiency: 'Efficiency',
    efficiencySub: 'sleep / time in bed',
    debt: 'Sleep debt tonight',
    debtNone: 'none',
    debtSub: 'vs 8 h norm',
    spread: 'Bedtime spread',
    spreadNone: 'not enough history',
    spreadSub: (nights) => `over ${nights} nights`,
    breakdown: 'How the score adds up',
    weight: 'weight',
    missing: (reason) => `no data — ${reason}; its weight is shared by the others`,
    penalties: 'Penalties:',
    tips: 'What to improve',
  },
  history: {
    title: 'History and trend',
    subtitle: (n) => `Last ${n} saved nights`,
    view: 'History view',
    chart: 'Chart',
    table: 'Table',
    loading: 'Loading history…',
    unavailable: 'History is unavailable: the database is not responding. Scoring still works, just without consistency.',
    empty: 'No saved nights yet. Score your sleep with “Save to history” on and a trend chart will appear here.',
    avg7: 'Average score · 7 days',
    avg30: 'Average score · 30 days',
    nights: (n) => `${n} night${n === 1 ? '' : 's'}`,
    trend: 'Trend',
    trendSub: (prev) => `vs previous week (${prev})`,
    trendNone: 'needs 2 weeks of records',
    debtWeek: 'Sleep debt this week',
    debtNone: 'none',
    debtSub: (norm) => `vs ${norm} h per night`,
    legendNight: 'nightly score',
    legendAvg: '7-day average',
    caption: 'Gridlines mark category boundaries: fair from 50, good from 70, excellent from 85.',
    chartLabel: (n) => `Sleep score chart for ${n} nights. Use the left and right arrow keys to move between nights.`,
    tipSleep: 'sleep',
    columns: {
      date: 'Date',
      times: 'Bedtime — wake-up',
      sleep: 'Sleep',
      waso: 'WASO',
      awakenings: 'Awakenings',
      score: 'Score',
      category: 'Category',
    },
  },
  errors: {
    network: 'The server is not responding. Is the backend running?',
    saveUnavailable: "The database is unavailable, so the night wasn't saved. Untick “Save to history” or try again later.",
    unknown: (status) => `API error (${status})`,
    validation: {
      greater_than_equal: ({ ge }) => `Must be at least ${ge}`,
      less_than_equal: ({ le }) => `Must be at most ${le}`,
      greater_than: ({ gt }) => `Must be greater than ${gt}`,
      int_parsing: () => 'Enter a number',
      float_parsing: () => 'Enter a number',
      int_from_float: () => 'Enter a whole number',
      time_parsing: () => 'Invalid time',
      time_type: () => 'Invalid time',
      date_parsing: () => 'Invalid date',
      date_from_datetime_parsing: () => 'Invalid date',
      missing: () => 'Required',
      date_in_future: () => "The night can't be in the future",
      same_bed_and_wake: () => 'Bedtime and wake-up time are the same',
      sleep_exceeds_bed: ({ sleep_hours: s, in_bed_hours: b }) => `${s} h of sleep is longer than the time in bed (${b} h)`,
      waso_exceeds_bed: () => "Sleep plus WASO doesn't fit into the time in bed",
      stages_exceed_sleep: () => 'Deep and REM sleep together exceed total sleep',
    },
  },
};

export const STRINGS = { ru, en };

export const LangContext = createContext('ru');

export function useLang() {
  return useContext(LangContext);
}

export function useT() {
  return STRINGS[useContext(LangContext)];
}

// Язык при загрузке: ?lang=en в адресе → сохранённый выбор → язык браузера.
export function initialLang() {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get('lang');
    if (LANGUAGES.includes(fromUrl)) return fromUrl;
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (LANGUAGES.includes(saved)) return saved;
  } catch {
    // localStorage бывает недоступен (приватный режим и т. п.) — просто идём дальше
  }
  return (navigator.language || '').toLowerCase().startsWith('ru') ? 'ru' : 'en';
}

export function rememberLang(lang) {
  // Если язык пришёл из ?lang=…, обновляем и адрес — иначе после перезагрузки он перебьёт выбор.
  const url = new URL(window.location.href);
  if (url.searchParams.has('lang')) {
    url.searchParams.set('lang', lang);
    window.history.replaceState(null, '', url);
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // не сохранилось — не страшно, при следующем визите язык определится заново
  }
}

export function formatHours(hours, t) {
  const total = Math.round(hours * 60);
  const h = Math.floor(total / 60);
  const m = total % 60;
  return m ? `${h} ${t.units.h} ${m} ${t.units.min}` : `${h} ${t.units.h}`;
}

export function formatDate(iso, t, options = { day: 'numeric', month: 'long' }) {
  // Полдень, чтобы часовой пояс не сдвинул дату на соседний день.
  return new Date(`${iso}T12:00:00`).toLocaleDateString(t.locale, options);
}
