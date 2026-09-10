import { useState } from 'react';
import { localToday } from '../api';
import { formatHours, useT } from '../i18n';

// Значения по умолчанию — обычная ночь, чтобы можно было сразу нажать «Оценить».
const INITIAL = {
  sleep_date: localToday(),
  bedtime: '23:30',
  wake_time: '07:00',
  total_sleep_hours: '6.9',
  waso_minutes: '20',
  awakenings: '2',
  deep_sleep_minutes: '',
  rem_sleep_minutes: '',
  caffeine_after_14: false,
  screen_before_bed: false,
};

function minutesInBed(bedtime, wake) {
  if (!bedtime || !wake) return null;
  const toMinutes = (t) => {
    const [h, m] = t.split(':').map(Number);
    return h * 60 + m;
  };
  // Подъём «раньше» отбоя — значит, перешли через полночь.
  return (toMinutes(wake) - toMinutes(bedtime) + 24 * 60) % (24 * 60);
}

function toPayload(values) {
  const optionalInt = (v) => (v === '' ? null : Number(v));
  return {
    sleep_date: values.sleep_date || null,
    bedtime: values.bedtime,
    wake_time: values.wake_time,
    total_sleep_hours: Number(String(values.total_sleep_hours).replace(',', '.')),
    waso_minutes: Number(values.waso_minutes || 0),
    awakenings: Number(values.awakenings || 0),
    deep_sleep_minutes: optionalInt(values.deep_sleep_minutes),
    rem_sleep_minutes: optionalInt(values.rem_sleep_minutes),
    caffeine_after_14: values.caffeine_after_14,
    screen_before_bed: values.screen_before_bed,
  };
}

function Field({ name, label, hint, error, children }) {
  return (
    <label className={`field${error ? ' field--error' : ''}`} htmlFor={name}>
      <span className="field__label">{label}</span>
      {children}
      {error ? (
        <span className="field__error" id={`${name}-error`}>
          {error}
        </span>
      ) : (
        hint && <span className="field__hint">{hint}</span>
      )}
    </label>
  );
}

export default function SleepForm({ onSubmit, loading, fieldErrors = {}, formErrors = [] }) {
  const t = useT();
  const [values, setValues] = useState(INITIAL);
  const [save, setSave] = useState(true);

  const set = (name) => (event) => {
    const { type, checked, value } = event.target;
    setValues((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const inBed = minutesInBed(values.bedtime, values.wake_time);
  const sleepHours = Number(String(values.total_sleep_hours).replace(',', '.'));
  const sleepExceedsBed = inBed !== null && sleepHours * 60 > inBed + 5;

  const input = (name, props) => (
    <input
      id={name}
      name={name}
      value={values[name]}
      onChange={set(name)}
      aria-invalid={Boolean(fieldErrors[name])}
      aria-describedby={fieldErrors[name] ? `${name}-error` : undefined}
      {...props}
    />
  );

  const handleSubmit = (event) => {
    event.preventDefault();
    onSubmit(toPayload(values), save);
  };

  return (
    <form className="card sleep-form" onSubmit={handleSubmit} noValidate>
      <h2 className="card__title">{t.form.title}</h2>

      <fieldset>
        <legend>{t.form.schedule}</legend>
        <div className="grid grid--2">
          <Field name="sleep_date" label={t.form.date} error={fieldErrors.sleep_date}>
            {input('sleep_date', { type: 'date', max: localToday() })}
          </Field>
          <Field
            name="total_sleep_hours"
            label={t.form.sleepHours}
            error={fieldErrors.total_sleep_hours || (sleepExceedsBed && t.form.sleepExceedsBed)}
            hint={t.form.sleepHint}
          >
            {input('total_sleep_hours', { type: 'number', min: 0, max: 24, step: 'any', inputMode: 'decimal', required: true })}
          </Field>
          <Field name="bedtime" label={t.form.bedtime} error={fieldErrors.bedtime}>
            {input('bedtime', { type: 'time', required: true })}
          </Field>
          <Field
            name="wake_time"
            label={t.form.wake}
            error={fieldErrors.wake_time}
            hint={inBed ? t.form.inBed(formatHours(inBed / 60, t)) : null}
          >
            {input('wake_time', { type: 'time', required: true })}
          </Field>
        </div>
      </fieldset>

      <fieldset>
        <legend>{t.form.awake}</legend>
        <div className="grid grid--2">
          <Field name="waso_minutes" label={t.form.waso} hint={t.form.wasoHint} error={fieldErrors.waso_minutes}>
            {input('waso_minutes', { type: 'number', min: 0, max: 1440, step: 1, inputMode: 'numeric' })}
          </Field>
          <Field name="awakenings" label={t.form.awakenings} error={fieldErrors.awakenings}>
            {input('awakenings', { type: 'number', min: 0, max: 100, step: 1, inputMode: 'numeric' })}
          </Field>
        </div>
      </fieldset>

      <fieldset>
        <legend>
          {t.form.stages} <span className="muted">{t.form.stagesNote}</span>
        </legend>
        <div className="grid grid--2">
          <Field name="deep_sleep_minutes" label={t.form.deep} error={fieldErrors.deep_sleep_minutes}>
            {input('deep_sleep_minutes', { type: 'number', min: 0, step: 1, inputMode: 'numeric', placeholder: t.form.unknown })}
          </Field>
          <Field name="rem_sleep_minutes" label={t.form.rem} error={fieldErrors.rem_sleep_minutes}>
            {input('rem_sleep_minutes', { type: 'number', min: 0, step: 1, inputMode: 'numeric', placeholder: t.form.unknown })}
          </Field>
        </div>
      </fieldset>

      <fieldset>
        <legend>{t.form.evening}</legend>
        <label className="check">
          <input type="checkbox" checked={values.caffeine_after_14} onChange={set('caffeine_after_14')} />
          {t.form.caffeine} <span className="muted">−5</span>
        </label>
        <label className="check">
          <input type="checkbox" checked={values.screen_before_bed} onChange={set('screen_before_bed')} />
          {t.form.screen} <span className="muted">−3</span>
        </label>
      </fieldset>

      {formErrors.length > 0 && (
        <div className="alert" role="alert">
          {formErrors.map((message) => (
            <p key={message}>{message}</p>
          ))}
        </div>
      )}

      <div className="sleep-form__actions">
        <label className="check">
          <input type="checkbox" checked={save} onChange={(e) => setSave(e.target.checked)} />
          {t.form.save}
        </label>
        <button type="submit" className="button" disabled={loading}>
          {loading ? t.form.submitting : t.form.submit}
        </button>
      </div>
    </form>
  );
}
