import { formatDate, formatHours, useT } from '../i18n';

const THRESHOLDS = [50, 70, 85]; // границы категорий poor / fair / good / excellent
const WEIGHTS = { duration: 20, efficiency: 25, continuity: 25, stages: 15, consistency: 15 };
// Категория — это статус: цвет всегда вместе со значком и подписью.
const CATEGORY_STATUS = {
  excellent: { icon: '✓', status: 'good' },
  good: { icon: '✓', status: 'good' },
  fair: { icon: '!', status: 'warning' },
  poor: { icon: '✕', status: 'critical' },
};

const pct = (value) => `${Math.round(value * 100)}%`;

// Совет относится к компоненту, штрафу или ни к чему конкретному.
function tipTag(component, t) {
  if (component in t.component) return t.component[component];
  if (component in t.penalty) return t.tipTag.penalty;
  return t.tipTag.general;
}

function CategoryChip({ category }) {
  const t = useT();
  const { icon, status } = CATEGORY_STATUS[category];
  return (
    <span className={`chip chip--${status}`}>
      <span className="chip__icon" aria-hidden="true">
        {icon}
      </span>
      {t.category[category]}
    </span>
  );
}

// Метр 0–100: засечки на границах категорий — это просветы цвета фона поверх полосы.
function ScoreMeter({ score }) {
  const t = useT();
  return (
    <div className="meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={score} aria-label={t.result.meter}>
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
  const t = useT();
  const { name, score, weight, applied_weight: applied } = component;
  const missing = score === null;
  const reweighted = !missing && Math.round(applied * 100) !== Math.round(weight * 100);
  return (
    <li className={`component${missing ? ' component--missing' : ''}`}>
      <div className="component__top">
        <span className="component__name">
          {t.component[name]} <span className="component__hint">{t.componentHint[name]}</span>
        </span>
        <span className="component__value">{missing ? '—' : Math.round(score)}</span>
      </div>
      <div className="bar" aria-hidden="true">
        {!missing && <div className="bar__fill" style={{ width: `${score}%` }} />}
      </div>
      <div className="component__meta">
        {missing
          ? t.result.missing(t.missingReason[name])
          : `${t.result.weight} ${pct(weight)}${reweighted ? ` → ${pct(applied)}` : ''}`}
      </div>
    </li>
  );
}

function Placeholder() {
  const t = useT();
  return (
    <section className="card result result--empty" aria-live="polite">
      <h2 className="card__title">{t.result.emptyTitle}</h2>
      <p className="muted">{t.result.emptyText}</p>
      <ul className="weights">
        {Object.entries(WEIGHTS).map(([name, weight]) => (
          <li key={name}>
            <span>{t.component[name]}</span>
            <span className="muted">{t.componentHint[name]}</span>
            <span className="weights__value">{weight}%</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function ResultCard({ result }) {
  const t = useT();
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
        {t.result.nightOf(formatDate(date, t))} ·{' '}
        {result.saved ? (result.replaced_existing ? t.result.replaced : t.result.saved) : t.result.notSaved}
      </p>

      <ScoreMeter score={score} />
      {cap !== null && (
        <p className="note">{t.result.cap(cap)}</p>
      )}

      <div className="stats">
        <Stat label={t.result.inBed} value={formatHours(result.time_in_bed_hours, t)} />
        <Stat label={t.result.efficiency} value={`${Math.round(result.sleep_efficiency)}%`} sub={t.result.efficiencySub} />
        <Stat
          label={t.result.debt}
          value={result.sleep_debt_hours > 0 ? formatHours(result.sleep_debt_hours, t) : t.result.debtNone}
          sub={t.result.debtSub}
        />
        <Stat
          label={t.result.spread}
          value={result.bedtime_sd_minutes === null ? '—' : `±${Math.round(result.bedtime_sd_minutes)} ${t.units.min}`}
          sub={
            result.bedtime_sd_minutes === null
              ? t.result.spreadNone
              : t.result.spreadSub(result.history_nights_used + 1)
          }
        />
      </div>

      <h3 className="section-title">{t.result.breakdown}</h3>
      <ul className="components">
        {components.map((c) => (
          <ComponentRow key={c.name} component={c} />
        ))}
      </ul>
      {penalties.length > 0 && (
        <p className="penalties">
          {t.result.penalties}{' '}
          {penalties.map((p) => (
            <span key={p.name} className="penalty">
              {t.penalty[p.name]} −{p.points}
            </span>
          ))}
        </p>
      )}

      <h3 className="section-title">{t.result.tips}</h3>
      <ol className="tips">
        {recommendations.map((tip) => (
          <li key={tip.text} className="tip">
            <div>
              <span className="tip__tag">{tipTag(tip.component, t)}</span>
              {tip.text}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
