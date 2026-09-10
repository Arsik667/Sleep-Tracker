import { useEffect, useRef, useState } from 'react';
import { ApiError, checkSleep, errorMessage, validationMessages } from './api';
import HistoryChart from './components/HistoryChart';
import ResultCard from './components/ResultCard';
import SleepForm from './components/SleepForm';
import { LANGUAGES, LangContext, STRINGS, initialLang, rememberLang } from './i18n';

// Ошибку храним «сырой» и переводим при отрисовке — тогда после смены языка она тоже на новом языке.
function describeError(error, t) {
  if (!error) return { fields: {}, general: [] };
  if (error.status === 422) return validationMessages(error.detail, t);
  if (error.status === 503) return { fields: {}, general: [t.errors.saveUnavailable] };
  return { fields: {}, general: [error instanceof ApiError ? errorMessage(error, t) : String(error.message)] };
}

export default function App() {
  const [lang, setLang] = useState(initialLang);
  const [result, setResult] = useState(null);
  const [lastNight, setLastNight] = useState(null); // последняя оценённая ночь — для перевода советов
  const [loading, setLoading] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [historyVersion, setHistoryVersion] = useState(0); // +1 после сохранения — история перезагрузится
  const resultRef = useRef(null);
  const langRequest = useRef(0);
  const t = STRINGS[lang];

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const handleSubmit = async (night, save) => {
    setLoading(true);
    setSubmitError(null);
    try {
      setResult(await checkSleep(night, save, lang));
      setLastNight(night);
      if (save) setHistoryVersion((v) => v + 1);
      // В одну колонку карточка результата оказывается под формой — прокручиваем к ней.
      if (window.matchMedia('(max-width: 899px)').matches) {
        requestAnimationFrame(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
      }
    } catch (error) {
      setSubmitError(error);
    } finally {
      setLoading(false);
    }
  };

  // Советы приходят с бэкенда на языке запроса. При смене языка переспрашиваем их для той же
  // ночи без сохранения (оценка от этого не меняется), а статус сохранения оставляем прежним.
  const changeLang = async (next) => {
    setLang(next);
    rememberLang(next);
    if (!lastNight) return;
    const request = ++langRequest.current;
    try {
      const fresh = await checkSleep(lastNight, false, next);
      if (request !== langRequest.current) return; // пока ждали, язык успели переключить ещё раз
      setResult((prev) =>
        prev && { ...fresh, saved: prev.saved, entry_id: prev.entry_id, replaced_existing: prev.replaced_existing }
      );
    } catch {
      // не получилось — останутся советы на прошлом языке, остальной интерфейс уже переведён
    }
  };

  const { fields: fieldErrors, general: formErrors } = describeError(submitError, t);

  return (
    <LangContext.Provider value={lang}>
      <div className="app">
        <header className="app__header">
          <div>
            <h1>
              <span aria-hidden="true">🌙</span> SleepTrack
            </h1>
            <p>{t.app.tagline}</p>
          </div>
          <div className="segmented" role="group" aria-label={t.app.language}>
            {LANGUAGES.map((code) => (
              <button key={code} type="button" lang={code} aria-pressed={lang === code} onClick={() => changeLang(code)}>
                {code.toUpperCase()}
              </button>
            ))}
          </div>
        </header>

        <main className="layout">
          <SleepForm onSubmit={handleSubmit} loading={loading} fieldErrors={fieldErrors} formErrors={formErrors} />
          <div ref={resultRef}>
            <ResultCard result={result} />
          </div>
        </main>

        <HistoryChart refreshKey={historyVersion} />

        <footer className="app__footer">{t.app.footer}</footer>
      </div>
    </LangContext.Provider>
  );
}
