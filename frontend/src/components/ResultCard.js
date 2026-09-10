import { CATEGORY, COMPONENT, COMPONENT_HINT, MISSING_REASON, PENALTY, TIP_TAG, formatDate, formatHours } from '../labels';

const THRESHOLDS = [50, 70, 85]; // границы категорий poor / fair / good / excellent
const WEIGHTS = { duration: 20, efficiency: 25, continuity: 25, stages: 15, consistency: 15 };

const pct = (value) => `${Math.round(value * 100)}%`;

function CategoryChip({ category }) {
  const { label, icon, status } = CATEGORY[category];
  return (
    <span className={`chip chip--${status}`}>
      <span className="chip__icon" aria-hidden="true">
        {icon}
      </span>
      {label}
    </span>
  );
}

// Метр 0–100: засечки на границах категорий — это просветы цвета фона поверх полосы.
function ScoreMeter({ score }) {
  return (
    <div className="meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={score} aria-label="Оценка сна">
      <div className="meter__track">
        <div className="meter__fill" style={{ width: `${score}%` }} />
        {THRESHOLDS.map((t) => (
          <span key={t} className="meter__tick" style={{ left: `${t}%` }} />
        ))}
      </div>
      {THRESHOLDS.map((t) => (
        <span key={t} className="meter__label" style={{ left: `${t}%` }}>
          {t}
        </span>
      ))}
    </div>
  );
}

function Stat({ label, value, sub }) {
  return (
    <div className="stat">
      <div className="stat__label">{label}</div>
      <div className="stat__value">{value}</div>
      {sub && <div className="stat__sub">{sub}</div>}
    </div>
  );
}

function ComponentRow({ component }) {
  const { name, score, weight, applied_weight: applied } = component;
  const missing = score === null;
  const reweighted = !missing && Math.round(applied * 100) !== Math.round(weight * 100);
  return (
    <li className={`component${missing ? ' component--missing' : ''}`}>
      <div className="component__top">
        <span className="component__name">
          {COMPONENT[name]} <span className="component__hint">{COMPONENT_HINT[name]}</span>
        </span>
        <span className="component__value">{missing ? '—' : Math.round(score)}</span>
      </div>
      <div className="bar" aria-hidden="true">
        {!missing && <div className="bar__fill" style={{ width: `${score}%` }} />}
      </div>
      <div className="component__meta">
        {missing
          ? `нет данных — ${MISSING_REASON[name]}, вес разделён между остальными`
          : `вес ${pct(weight)}${reweighted ? ` → ${pct(applied)}` : ''}`}
      </div>
    </li>
  );
}

function Placeholder() {
  return (
    <section className="card result result--empty" aria-live="polite">
      <h2 className="card__title">Оценка появится здесь</h2>
      <p className="muted">
        Заполните форму и нажмите «Оценить сон». Итог 0–100 складывается из пяти компонентов, а кофеин и экран перед
        сном снимают баллы.
      </p>
      <ul className="weights">
        {Object.entries(WEIGHTS).map(([name, weight]) => (
          <li key={name}>
            <span>{COMPONENT[name]}</span>
            <span className="muted">{COMPONENT_HINT[name]}</span>
            <span className="weights__value">{weight}%</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function ResultCard({ result }) {
  if (!result) return <Placeholder />;

  const {
    score, category, components, penalties, score_cap: cap, recommendations, sleep_date: date,
  } = result;

  return (
    <section className="card result" aria-live="polite">
      <div className="result__head">
        <div className="hero">
          <span className="hero__value">{score}</span>
          <span className="hero__max">/ 100</span>
        </div>
        <CategoryChip category={category} />
      </div>
      <p className="result__caption">
        Ночь на {formatDate(date)} ·{' '}
        {result.saved
          ? result.replaced_existing
            ? 'сохранено, прошлая запись за эту дату заменена'
            : 'сохранено в историю'
          : 'не сохранено'}
      </p>

      <ScoreMeter score={score} />
      {cap !== null && (
        <p className="note">Оценка ограничена {cap} баллами: при таком коротком сне выше не бывает.</p>
      )}

      <div className="stats">
        <Stat label="В постели" value={formatHours(result.time_in_bed_hours)} />
        <Stat label="Эффективность" value={`${Math.round(result.sleep_efficiency)}%`} sub="сон / время в постели" />
        <Stat
          label="Недосып за ночь"
          value={result.sleep_debt_hours > 0 ? formatHours(result.sleep_debt_hours) : 'нет'}
          sub="от нормы 8 ч"
        />
        <Stat
          label="Разброс отбоя"
          value={result.bedtime_sd_minutes === null ? '—' : `±${Math.round(result.bedtime_sd_minutes)} мин`}
          sub={
            result.bedtime_sd_minutes === null
              ? 'мало истории'
              : `по ${result.history_nights_used + 1} ночам`
          }
        />
      </div>

      <h3 className="section-title">Из чего сложилась оценка</h3>
      <ul className="components">
        {components.map((c) => (
          <ComponentRow key={c.name} component={c} />
        ))}
      </ul>
      {penalties.length > 0 && (
        <p className="penalties">
          Штрафы:{' '}
          {penalties.map((p) => (
            <span key={p.name} className="penalty">
              {PENALTY[p.name]} −{p.points}
            </span>
          ))}
        </p>
      )}

      <h3 className="section-title">Что можно улучшить</h3>
      <ol className="tips">
        {recommendations.map((tip) => (
          <li key={tip.text} className="tip">
            <div>
              <span className="tip__tag">{TIP_TAG[tip.component] ?? tip.component}</span>
              {tip.text}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
