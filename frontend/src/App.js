import { useRef, useState } from 'react';
import { ApiError, checkSleep, validationMessages } from './api';
import HistoryChart from './components/HistoryChart';
import ResultCard from './components/ResultCard';
import SleepForm from './components/SleepForm';

export default function App() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});
  const [formErrors, setFormErrors] = useState([]);
  const [historyVersion, setHistoryVersion] = useState(0); // +1 после сохранения — история перезагрузится
  const resultRef = useRef(null);

  const handleSubmit = async (night, save) => {
    setLoading(true);
    setFieldErrors({});
    setFormErrors([]);
    try {
      setResult(await checkSleep(night, save));
      if (save) setHistoryVersion((v) => v + 1);
      // В одну колонку карточка результата оказывается под формой — прокручиваем к ней.
      if (window.matchMedia('(max-width: 899px)').matches) {
        requestAnimationFrame(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        const { fields, general } = validationMessages(error.detail);
        setFieldErrors(fields);
        setFormErrors(general);
      } else {
        setFormErrors([error.message]);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="app__header">
        <h1>
          <span aria-hidden="true">🌙</span> SleepTrack
        </h1>
        <p>Оценка качества сна за ночь, советы по слабым местам и тренд по истории.</p>
      </header>

      <main className="layout">
        <SleepForm onSubmit={handleSubmit} loading={loading} fieldErrors={fieldErrors} formErrors={formErrors} />
        <div ref={resultRef}>
          <ResultCard result={result} />
        </div>
      </main>

      <HistoryChart refreshKey={historyVersion} />

      <footer className="app__footer">
        SleepTrack — учебный проект, а не медицинский инструмент. Если сон плохой неделями, стоит обратиться к врачу.
      </footer>
    </div>
  );
}
