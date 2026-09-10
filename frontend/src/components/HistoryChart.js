import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { errorMessage, fetchHistory, fetchSummary, localToday } from '../api';
import { formatDate, formatHours, useT } from '../i18n';

const HISTORY_LIMIT = 30;
const ROLLING_DAYS = 7;
const HEIGHT = 240; // вместе с полосой подписей оси X — чтобы у карточки не было своей прокрутки
const MARGIN = { top: 12, right: 40, bottom: 28, left: 32 };
const THRESHOLDS = [50, 70, 85]; // границы категорий — линии сетки
const TOOLTIP_WIDTH = 220;

// Даты — в «номерах дней» по UTC: так разница между датами не зависит от перехода на летнее время.
const dayNumber = (iso) => {
  const [y, m, d] = iso.split('-').map(Number);
  return Date.UTC(y, m - 1, d) / 86400000;
};
const isoFromDay = (day) => new Date(day * 86400000).toISOString().slice(0, 10);

// Ночи от старых к новым + скользящее среднее за 7 дней (по датам, а не по числу записей).
function buildPoints(entries) {
  const sorted = [...entries].sort((a, b) => a.sleep_date.localeCompare(b.sleep_date));
  return sorted.map((entry) => {
    const day = dayNumber(entry.sleep_date);
    const window = sorted.filter((e) => {
      const d = dayNumber(e.sleep_date);
      return d > day - ROLLING_DAYS && d <= day;
    });
    const avg = window.reduce((sum, e) => sum + e.score, 0) / window.length;
    return { ...entry, day, avg };
  });
}

function useWidth(ref) {
  const [width, setWidth] = useState(0);
  // useLayoutEffect + синхронный замер: график рисуется сразу нужной ширины, без мигания;
  // ResizeObserver дальше только следит за изменением размера.
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return undefined;
    setWidth(element.getBoundingClientRect().width);
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}

// Не больше одной подписи даты на ~80 px — на телефоне их меньше, чтобы не слипались.
function xTicks(d0, d1, plotWidth) {
  if (d0 === d1) return [d0];
  const maxTicks = Math.max(2, Math.min(6, Math.floor(plotWidth / 80)));
  const step = Math.max(1, Math.ceil((d1 - d0) / (maxTicks - 1)));
  const ticks = [];
  for (let d = d0; d <= d1; d += step) ticks.push(d);
  return ticks;
}

function TrendChart({ entries }) {
  const t = useT();
  const wrapRef = useRef(null);
  const width = useWidth(wrapRef);
  const [active, setActive] = useState(null);
  const points = useMemo(() => buildPoints(entries), [entries]);

  const plotW = Math.max(0, width - MARGIN.left - MARGIN.right);
  const plotH = HEIGHT - MARGIN.top - MARGIN.bottom;
  const d0 = points[0].day;
  const d1 = points[points.length - 1].day;
  const x = (day) => MARGIN.left + (d1 === d0 ? plotW / 2 : ((day - d0) / (d1 - d0)) * plotW);
  // Низ шкалы — не выше 40 и с запасом под худшую ночь: иначе при баллах 60–95
  // половина графика пустует и тренд сжимается в полоску. Ось подписана, так что это честно.
  const minScore = Math.min(...points.map((p) => p.score));
  const floor = Math.max(0, Math.min(40, Math.floor((minScore - 5) / 10) * 10));
  const y = (score) => MARGIN.top + (1 - (score - floor) / (100 - floor)) * plotH;
  const grid = [floor, ...THRESHOLDS.filter((t) => t > floor), 100];

  // Линия среднего рвётся на пропусках ≥ 7 дней: среднее там «начинается заново».
  const avgPaths = [];
  points.forEach((p, i) => {
    const command = `${x(p.day).toFixed(1)},${y(p.avg).toFixed(1)}`;
    if (i === 0 || p.day - points[i - 1].day >= ROLLING_DAYS) avgPaths.push(`M${command}`);
    else avgPaths[avgPaths.length - 1] += ` L${command}`;
  });

  const nearest = (clientX) => {
    const left = wrapRef.current.getBoundingClientRect().left;
    const px = clientX - left;
    let best = 0;
    points.forEach((p, i) => {
      if (Math.abs(x(p.day) - px) < Math.abs(x(points[best].day) - px)) best = i;
    });
    return best;
  };

  const onKeyDown = (event) => {
    const last = points.length - 1;
    const moves = { ArrowLeft: -1, ArrowRight: 1 };
    if (event.key in moves) {
      event.preventDefault();
      setActive((i) => Math.min(last, Math.max(0, (i ?? last) + moves[event.key])));
    } else if (event.key === 'Home') setActive(0);
    else if (event.key === 'End') setActive(last);
    else if (event.key === 'Escape') setActive(null);
  };

  const current = active !== null ? points[active] : null;
  const lastPoint = points[points.length - 1];

  // Подсказка — справа от перекрестья, если не влезает — слева, а на узком экране
  // просто зажимается в границах графика (иначе появится горизонтальная прокрутка).
  const tipWidth = Math.min(TOOLTIP_WIDTH, width);
  let tipLeft = 0;
  if (current) {
    const cx = x(current.day);
    if (cx + 12 + tipWidth <= width) tipLeft = cx + 12;
    else if (cx - 12 - tipWidth >= 0) tipLeft = cx - 12 - tipWidth;
    else tipLeft = Math.max(0, Math.min(width - tipWidth, cx - tipWidth / 2));
  }

  return (
    <div
      ref={wrapRef}
      className="chart"
      style={{ height: HEIGHT }}
      tabIndex={0}
      role="img"
      aria-label={t.history.chartLabel(points.length)}
      onKeyDown={onKeyDown}
      onFocus={() => setActive((i) => i ?? points.length - 1)}
      onBlur={() => setActive(null)}
    >
      {width > 0 && (
        <svg width={width} height={HEIGHT} aria-hidden="true">
          {grid.map((g) => (
            <g key={g}>
              <line className={g === floor ? 'chart__axis' : 'chart__grid'} x1={MARGIN.left} x2={width - MARGIN.right} y1={y(g)} y2={y(g)} />
              <text className="chart__tick" x={MARGIN.left - 8} y={y(g)} dy="0.32em" textAnchor="end">
                {g}
              </text>
            </g>
          ))}
          {xTicks(d0, d1, plotW).map((d) => (
            <text key={d} className="chart__tick" x={x(d)} y={HEIGHT - 8} textAnchor="middle">
              {formatDate(isoFromDay(d), t, { day: 'numeric', month: 'short' })}
            </text>
          ))}

          {current && <line className="chart__crosshair" x1={x(current.day)} x2={x(current.day)} y1={MARGIN.top} y2={MARGIN.top + plotH} />}

          {points.map((p, i) => (
            <circle
              key={p.sleep_date}
              className={`chart__dot${i === active ? ' chart__dot--active' : ''}`}
              cx={x(p.day)}
              cy={y(p.score)}
              r={i === active ? 6 : 4}
            />
          ))}
          {avgPaths.map((d) => (
            <path key={d} className="chart__avg" d={d} />
          ))}
          {current && <circle className="chart__avg-dot" cx={x(current.day)} cy={y(current.avg)} r={4} />}

          {/* Прямая подпись конца линии тренда — значение, которое читают первым. */}
          <text className="chart__end-label" x={x(lastPoint.day) + 8} y={y(lastPoint.avg)} dy="0.32em">
            {Math.round(lastPoint.avg)}
          </text>

          {/* Прозрачная зона наведения на весь график: указатель ищет ближайшую дату, а не точку. */}
          <rect
            x={MARGIN.left}
            y={0}
            width={plotW}
            height={HEIGHT}
            fill="transparent"
            onPointerMove={(e) => setActive(nearest(e.clientX))}
            onPointerLeave={() => setActive(null)}
          />
        </svg>
      )}

      {current && (
        <div
          className="tooltip"
          // По вертикали — в той половине графика, где нет выбранной точки,
          // чтобы подсказка не закрывала данные и плитки сверху.
          style={{
            width: tipWidth,
            left: tipLeft,
            ...(current.score >= (floor + 100) / 2 ? { bottom: MARGIN.bottom + 6 } : { top: MARGIN.top }),
          }}
        >
          <div className="tooltip__date">
            {formatDate(current.sleep_date, t, { weekday: 'short', day: 'numeric', month: 'long' })}
          </div>
          <div className="tooltip__row">
            <span className="tooltip__key tooltip__key--dot" />
            <strong>{current.score}</strong> {t.category[current.category].toLowerCase()}
          </div>
          <div className="tooltip__row">
            <span className="tooltip__key tooltip__key--line" />
            <strong>{Math.round(current.avg)}</strong> {t.history.legendAvg}
          </div>
          <div className="tooltip__meta">
            {t.history.tipSleep} {formatHours(current.total_sleep_hours, t)} · {current.bedtime.slice(0, 5)}–
            {current.wake_time.slice(0, 5)}
          </div>
        </div>
      )}
    </div>
  );
}

function HistoryTable({ entries }) {
  const t = useT();
  const col = t.history.columns;
  return (
    <div className="table-wrap">
      <table className="history-table">
        <thead>
          <tr>
            <th>{col.date}</th>
            <th>{col.times}</th>
            <th className="num">{col.sleep}</th>
            <th className="num">{col.waso}</th>
            <th className="num">{col.awakenings}</th>
            <th className="num">{col.score}</th>
            <th>{col.category}</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id}>
              <td>{formatDate(e.sleep_date, t, { day: 'numeric', month: 'short', weekday: 'short' })}</td>
              <td>
                {e.bedtime.slice(0, 5)} — {e.wake_time.slice(0, 5)}
              </td>
              <td className="num">{formatHours(e.total_sleep_hours, t)}</td>
              <td className="num">
                {e.waso_minutes} {t.units.min}
              </td>
              <td className="num">{e.awakenings}</td>
              <td className="num">
                <strong>{e.score}</strong>
              </td>
              <td>{t.category[e.category]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SummaryTiles({ summary }) {
  const t = useT();
  const h = t.history;
  const { avg_score_7d: avg7, avg_score_30d: avg30, trend } = summary;
  const arrow = { up: '↑', down: '↓', flat: '→' }[trend.direction];
  const sign = trend.delta > 0 ? '+' : trend.delta < 0 ? '−' : '±';
  return (
    <div className="stats stats--summary">
      <div className="stat">
        <div className="stat__label">{h.avg7}</div>
        <div className="stat__value">{avg7 === null ? '—' : Math.round(avg7)}</div>
        <div className="stat__sub">{h.nights(summary.nights_7d)}</div>
      </div>
      <div className="stat">
        <div className="stat__label">{h.avg30}</div>
        <div className="stat__value">{avg30 === null ? '—' : Math.round(avg30)}</div>
        <div className="stat__sub">{h.nights(summary.nights_30d)}</div>
      </div>
      <div className="stat">
        <div className="stat__label">{h.trend}</div>
        <div className={`stat__value delta delta--${trend.direction ?? 'none'}`}>
          {trend.direction ? `${arrow} ${sign}${Math.abs(trend.delta)}` : '—'}
        </div>
        <div className="stat__sub">
          {trend.direction ? h.trendSub(Math.round(trend.avg_score_prev_7d)) : h.trendNone}
        </div>
      </div>
      <div className="stat">
        <div className="stat__label">{h.debtWeek}</div>
        <div className="stat__value">
          {summary.sleep_debt_week_hours > 0 ? formatHours(summary.sleep_debt_week_hours, t) : h.debtNone}
        </div>
        <div className="stat__sub">{h.debtSub(summary.sleep_norm_hours)}</div>
      </div>
    </div>
  );
}

export default function HistoryChart({ refreshKey }) {
  const t = useT();
  const [data, setData] = useState(null); // { entries, summary }
  const [error, setError] = useState(null); // ApiError — текст выбираем при отрисовке, на текущем языке
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState('chart');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([fetchHistory(HISTORY_LIMIT), fetchSummary(localToday())])
      .then(([entries, summary]) => {
        if (cancelled) return;
        setData({ entries, summary });
        setError(null);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const entries = data?.entries ?? [];

  return (
    // При перезагрузке держим прошлую отрисовку полупрозрачной — без скачков и скелетонов.
    <section className={`card history${loading && data ? ' history--loading' : ''}`}>
      <div className="history__head">
        <div>
          <h2 className="card__title">{t.history.title}</h2>
          <p className="history__subtitle">{t.history.subtitle(HISTORY_LIMIT)}</p>
        </div>
        {entries.length > 0 && (
          <div className="segmented" role="group" aria-label={t.history.view}>
            <button type="button" aria-pressed={view === 'chart'} onClick={() => setView('chart')}>
              {t.history.chart}
            </button>
            <button type="button" aria-pressed={view === 'table'} onClick={() => setView('table')}>
              {t.history.table}
            </button>
          </div>
        )}
      </div>

      {error && (
        <p className="alert" role="alert">
          {error.status === 503 ? t.history.unavailable : errorMessage(error, t)}
        </p>
      )}
      {!data && !error && <p className="muted">{t.history.loading}</p>}

      {data && (
        <>
          <SummaryTiles summary={data.summary} />
          {entries.length === 0 ? (
            <p className="empty">{t.history.empty}</p>
          ) : view === 'chart' ? (
            <figure className="chart-figure">
              <div className="legend">
                <span className="legend__item">
                  <svg width="12" height="12" aria-hidden="true">
                    <circle cx="6" cy="6" r="4" className="chart__dot" />
                  </svg>
                  {t.history.legendNight}
                </span>
                <span className="legend__item">
                  <svg width="18" height="12" aria-hidden="true">
                    <line x1="2" y1="6" x2="16" y2="6" className="chart__avg" />
                  </svg>
                  {t.history.legendAvg}
                </span>
              </div>
              <TrendChart entries={entries} />
              <figcaption className="chart-caption">{t.history.caption}</figcaption>
            </figure>
          ) : (
            <HistoryTable entries={entries} />
          )}
        </>
      )}
    </section>
  );
}
