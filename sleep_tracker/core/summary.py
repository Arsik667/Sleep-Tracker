"""Агрегаты по истории: средний балл за 7/30 дней, тренд и недосып за неделю.

Чистая функция над списком ночей — откуда они взялись (Postgres, SQLite, CSV
из фитнес-трекера), ей всё равно. Окна считаются по дате ночи включительно:
«7 дней» на 10 сентября — это ночи с 4 по 10 сентября.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from statistics import mean

from .sleep_score import SLEEP_NORM_HOURS

TREND_THRESHOLD = 3.0  # разница средних меньше этого — считаем, что тренда нет


@dataclass(frozen=True)
class NightRecord:
    sleep_date: date
    score: int
    total_sleep_hours: float


@dataclass(frozen=True)
class Trend:
    direction: str | None  # up / down / flat; None — не с чем сравнивать
    delta: float | None  # средний балл за 7 дней минус средний за предыдущие 7
    avg_score_prev_7d: float | None


@dataclass(frozen=True)
class HistorySummary:
    as_of: date
    avg_score_7d: float | None
    avg_score_30d: float | None
    nights_7d: int
    nights_30d: int
    sleep_debt_week_hours: float
    sleep_norm_hours: float
    trend: Trend

    def to_dict(self) -> dict:
        return asdict(self)


def summarize_history(
    records: Iterable[NightRecord], today: date, norm_hours: float = SLEEP_NORM_HOURS
) -> HistorySummary:
    records = list(records)
    last_7 = _window(records, today, days=7)
    prev_7 = _window(records, today - timedelta(days=7), days=7)
    last_30 = _window(records, today, days=30)

    avg_7 = _avg_score(last_7)
    avg_prev = _avg_score(prev_7)
    if avg_7 is None or avg_prev is None:
        trend = Trend(direction=None, delta=None, avg_score_prev_7d=avg_prev)
    else:
        delta = round(avg_7 - avg_prev, 1)
        direction = "up" if delta >= TREND_THRESHOLD else "down" if delta <= -TREND_THRESHOLD else "flat"
        trend = Trend(direction=direction, delta=delta, avg_score_prev_7d=avg_prev)

    return HistorySummary(
        as_of=today,
        avg_score_7d=avg_7,
        avg_score_30d=_avg_score(last_30),
        nights_7d=len(last_7),
        nights_30d=len(last_30),
        sleep_debt_week_hours=weekly_sleep_debt(last_7, norm_hours),
        sleep_norm_hours=norm_hours,
        trend=trend,
    )


def weekly_sleep_debt(records: Iterable[NightRecord], norm_hours: float = SLEEP_NORM_HOURS) -> float:
    """Сумма недосыпа по ночам относительно нормы.

    Намеренно консервативно: пересып в одну ночь не «гасит» недосып в другие,
    а ночи без записи не считаются — о них мы ничего не знаем.
    """
    return round(sum(max(0.0, norm_hours - r.total_sleep_hours) for r in records), 2)


def _window(records: list[NightRecord], end: date, days: int) -> list[NightRecord]:
    start = end - timedelta(days=days - 1)
    return [r for r in records if start <= r.sleep_date <= end]


def _avg_score(records: list[NightRecord]) -> float | None:
    return round(mean(r.score for r in records), 1) if records else None
